import logging
import cherrypy
import time
import json
import pickle
from cherrypy.process.plugins import Monitor
from sqlalchemy.orm import deferred
from sqlalchemy.exc import IntegrityError
from sqlalchemy import Column, Integer, String, BLOB, BigInteger, func
from sqlalchemy.dialects import mysql
from sqlalchemy.orm.exc import NoResultFound
from opmuse.database import Base, get_database, get_session


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

    def values(self):
        return self._storage.items()


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


class CachePlugin(Monitor):
    GC_AGE = 6 * 30 * 24 * 3600
    """
        How old an entry has to be considered stale and removed.
    """

    def __init__(self, bus):
        Monitor.__init__(self, bus, self.run, frequency = 20 * 60)

    def run(self):
        self._serialize()

    def start(self):
        self._gc(CachePlugin.GC_AGE)
        self._unserialize()

        Monitor.start(self)

    start.priority = 105

    def stop(self):
        self._serialize()

        Monitor.stop(self)

    stop.priority = 105

    def _gc(self, age):
        database = get_session()

        now = int(time.time())

        updated_filter = "(%d - updated) > %d" % (now, age)

        item_count = database.query(func.count(CacheObject.id)).filter(updated_filter).scalar()

        database.query(CacheObject).filter(updated_filter).delete(synchronize_session='fetch')

        database.commit()
        database.remove()

        log("Garbage collected %d cache objects" % item_count)

    def _serialize(self):
        # TODO actually use "updated" var to see if we even need to serialize/persist the changes...

        database = get_session()

        item_count = 0

        for key, item in cache.storage.values():
            item_count += 1

            value = item['value']
            updated = item['updated']

            # we don't serialize Keep values, in case of restart they'll just try again...
            if value is Keep:
                continue

            count = (database.query(func.count(CacheObject.id))
                     .filter(CacheObject.key == key).scalar())

            orig_value = value

            if isinstance(value, object):
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
