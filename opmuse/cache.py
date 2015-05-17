# Copyright 2012-2015 Mattias Fliesberg
#
# This file is part of opmuse.
#
# opmuse is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# opmuse is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with opmuse.  If not, see <http://www.gnu.org/licenses/>.

import logging
import cherrypy
import time
import json
import pickle
import math
from cherrypy.process.plugins import Monitor
from sqlalchemy.orm import deferred
from sqlalchemy import Column, Integer, String, BLOB, BigInteger, func, text
from sqlalchemy.dialects import mysql
from opmuse.database import Base, get_session
from opmuse.sizeof import total_size


def debug(msg):
    cherrypy.log.error(msg, context='cache', severity=logging.DEBUG)


def log(msg):
    cherrypy.log(msg, context='cache')


class CacheObject(Base):
    __tablename__ = 'cache_objects'

    id = Column(Integer, primary_key=True)
    key = Column(String(255), index=True, unique=True)
    type = Column(String(128))
    updated = Column(BigInteger, index=True)
    value = deferred(Column(BLOB().with_variant(mysql.LONGBLOB(), 'mysql')))


class CacheStorage:
    def __init__(self):
        self._storage = {}

    def set(self, key, updated, value):
        if value is Keep and key in self._storage:
            value = self._storage[key]['value']

        self._storage[key] = {
            'value': value,
            'updated': updated
        }

    def get_updated(self, key):
        if key in self._storage:
            return self._storage[key]['updated']

    def get_value(self, key):
        if key in self._storage:
            return self._storage[key]['value']

    def has(self, key):
        return key in self._storage

    def delete(self, key):
        if key in self._storage:
            del self._storage[key]

    def values(self):
        """
        Returns a shallow copy of dictionary's items, to avoid changes to _storage
        throwing a "RuntimeError: dictionary changed size during iteration" error
        but still referencing the same items thus saving memory.
        """
        return self._storage.copy().items()

    def size(self):
        return len(self._storage)


class Keep:
    pass


class Cache:
    KEEP_AGE = 30 * 60
    """
        For Keep values we ignore the provided age and use this instead if the
        provided age is larger than this value. The reason is that Keep values
        are only used to mark the key as used until the data is actually set
        (e.g. for slow bgtasks and such) so if that fails the Keep value is
        invalid and it's "safe" to try again.

        This only happens the first time a value is fetched because subsequent
        times it will just have left the already set value. But it only needs to
        happen the first time...
    """

    def __init__(self):
        self.storage = CacheStorage()

    def needs_update(self, key, age):
        now = int(time.time())

        if self.storage.has(key):
            value = self.storage.get_value(key)
            updated = self.storage.get_updated(key)

            if value is Keep and age > Cache.KEEP_AGE:
                _age = Cache.KEEP_AGE
            else:
                _age = age

            if now - updated > _age:
                return True
        else:
            return True

        return False

    def get(self, key):
        value = self.storage.get_value(key)

        if value is Keep:
            return None
        else:
            return value

    def keep(self, key):
        """
            Updates the timestamp of the objects and creates it if it doesn't exist
            but keeps the value if there is one.
        """

        self.set(key, Keep)

    def set(self, key, value):
        if value is not None and value is not Keep and not isinstance(value, (str, bytes, dict, list, object)):
            raise ValueError("Unsupported value type.")

        updated = int(time.time())

        self.storage.set(key, updated, value)

    def has(self, key):
        return self.storage.has(key)

    def delete(self, key):
        self.storage.delete(key)

    def call(self, method, args, age):
        """
            Calls method if new/old or uses cached value if not.
            Only supports caching on method name and not on args.
        """
        if not hasattr(method, '__self__'):
            raise ValueError('Unsupported method type, need @classmethod.')

        key = "%s.%s.%s" % (method.__module__, method.__self__.__name__, method.__name__)

        if self.needs_update(key, age):
            result = method(*args)
            self.set(key, result)
        else:
            result = self.get(key)

        return result


class CachePlugin(Monitor):
    FREQUENCY = 20 * 60
    """
    How often we should serialize what's in memory
    """

    GC_SIZE = 256 * 1024 * 1024
    """
        How big the cache can get before we start removing old objects.
    """

    GC_AGE = 3 * 30 * 24 * 3600
    """
        How old an entry has to be to be considered stale and removed.
    """

    GC_FREQUENCY = 24 * 60 * 60
    """
    How often we should gc. This is based on FREQUENCY so it will run at the same
    time as the nearest FREQUENCY run.
    """

    def __init__(self, bus):
        Monitor.__init__(self, bus, self.run, frequency=CachePlugin.FREQUENCY)
        self.index = 0

    def run(self):
        self.index += 1

        # run serialize first because _gc() uses the database to determine
        # what to delete from memory and database
        self._serialize()

        if self.index % math.floor(CachePlugin.GC_FREQUENCY / CachePlugin.FREQUENCY) == 0:
            self._gc()
            self.index = 0

    def start(self):
        self._gc()
        self._unserialize()

        Monitor.start(self)

    start.priority = 105

    def stop(self):
        self._serialize()

        Monitor.stop(self)

    stop.priority = 105

    def _gc(self):
        database = get_session()

        total_bytes_before = self._total_bytes()

        old_item_count = 0

        now = int(time.time())

        keys = []

        # remove old objects from memory
        for key, in (database.query(CacheObject.key)
                     .filter(text("(%d - updated) > %d" % (now, CachePlugin.GC_AGE))).all()):
            cache.delete(key)
            keys.append(key)
            old_item_count += 1

        # remove old objects from database
        if len(keys) > 0:
            database.query(CacheObject).filter(CacheObject.key.in_(keys)).delete(synchronize_session='fetch')

        database.commit()

        debug('Garbage collected %d old cache objects because of age' % old_item_count)

        big_item_count = 0

        # remove the 10 oldest cache objects until total cache size is below limit
        while True:
            total_bytes = self._total_bytes()

            if total_bytes > CachePlugin.GC_SIZE:
                keys = []

                # remove old oversized objects from memory
                for key, in database.query(CacheObject.key).order_by(CacheObject.updated.asc()).limit(10).all():
                    cache.delete(key)
                    keys.append(key)
                    big_item_count += 1

                # remove old oversized objects from database
                database.query(CacheObject).filter(CacheObject.key.in_(keys)).delete(synchronize_session='fetch')

                database.commit()
            else:
                break

        debug('Garbage collected %d old cache objects because of total cache size' % big_item_count)

        database.remove()

        log("Garbage collected %d cache objects, total cache size was %d kb and is now %d kb" %
            (old_item_count + big_item_count, total_bytes_before / 1024, total_bytes / 1024))

    def _total_bytes(self):
        total_bytes = 0

        for key, item in cache.storage.values():
            bytes = total_size(item['value'])
            total_bytes += bytes

        return total_bytes

    def _serialize(self):
        """
        Serialize cache objects to database.

        TODO actually use "updated" var to see if we even need to serialize/persist the changes...
        TODO lock cache storage while serializing?
        """

        database = get_session()

        item_count = 0

        for key, item in cache.storage.values():
            item_count += 1

            value = item['value']
            updated = item['updated']

            count = (database.query(func.count(CacheObject.id))
                     .filter(CacheObject.key == key).scalar())

            # Dont serialize Keep values, this is for example useful for bgtasks
            # that was added to the queue but never run because of a restart.
            # This way they will just be triggered again on the next start/use
            # and we dont have to wait for the Keep time to run out.
            if value is Keep:
                continue
            elif isinstance(value, object):
                value_type = 'object'
            else:
                value_type = type(value).__name__

            if value_type == 'object':
                value = pickle.dumps(value)
            elif value_type == 'str':
                value = value.encode()
            elif value_type == 'dict' or value_type == 'list':
                value = json.dumps(value).encode()

            if count > 0:
                parameters = {'updated': updated}

                parameters['value'] = value
                parameters['type'] = value_type

                database.query(CacheObject).filter(CacheObject.key == key).update(parameters)
            else:
                parameters = {'key': key, 'value': value, 'updated': updated, 'type': value_type}
                database.execute(CacheObject.__table__.insert(), parameters)

        database.commit()
        database.remove()

        log("Serialized %d cache objects" % item_count)

    def _unserialize(self):
        """
        Unserialize / load cache objects from database.
        """

        database = get_session()

        item_count = 0

        for object in database.query(CacheObject).all():
            item_count += 1

            if object.type == 'object':
                value = pickle.loads(object.value)
            elif object.type == 'str':
                value = object.value.decode()
            elif object.type == 'dict' or object.type == 'list':
                value = json.loads(object.value.decode())
            else:
                value = object.value

            cache.storage.set(object.key, object.updated, value)

        database.remove()

        log("Unserialized %d cache objects" % item_count)


cache = Cache()
