import time
import json
import pickle
from sqlalchemy.orm import deferred
from sqlalchemy.exc import IntegrityError
from sqlalchemy import Column, Integer, String, BLOB, BigInteger, func
from sqlalchemy.dialects import mysql
from sqlalchemy.orm.exc import NoResultFound
from opmuse.database import Base, get_database


class CacheObject(Base):
    __tablename__ = 'cache_objects'

    id = Column(Integer, primary_key=True)
    key = Column(String(255), index=True, unique=True)
    type = Column(String(128))
    updated = Column(BigInteger, index=True)
    value = deferred(Column(BLOB().with_variant(mysql.LONGBLOB(), 'mysql')))


class Keep:
    pass


class Cache:
    def needs_update(self, key, age):
        now = int(time.time())

        count = (get_database().query(func.count(CacheObject.id))
                 .filter(CacheObject.key == key).scalar())

        if count > 0:
            count = (get_database().query(func.count(CacheObject.id))
                     .filter(CacheObject.key == key).filter("(%d - updated) > %d" % (now, age)).scalar())

            return count > 0
        else:
            return True

    def get(self, key):
        try:
            object = get_database().query(CacheObject).filter(CacheObject.key == key).one()

            if object.type == 'object':
                return pickle.loads(object.value)
            elif object.type == 'str':
                return object.value.decode()
            elif object.type == 'dict' or object.type == 'list':
                return json.loads(object.value.decode())

            return object.value
        except NoResultFound:
            pass

    def keep(self, key):
        """
            Updates the timestamp of the objects and creates it if it doesn't exist
            but keeps the value if there is one.
        """

        self.set(key, Keep)

    def set(self, key, value):
        if value is not None and value is not Keep and not isinstance(value, (str, bytes, dict, list, object)):
            raise ValueError("Unsupported value type.")

        count = (get_database().query(func.count(CacheObject.id))
                 .filter(CacheObject.key == key).scalar())

        updated = int(time.time())

        orig_value = value

        if value is not Keep and isinstance(value, object):
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

            if value is not Keep:
                parameters['value'] = value
                parameters['type'] = value_type

            get_database().query(CacheObject).filter(CacheObject.key == key).update(parameters)
        else:
            if value is Keep:
                value = None
                value_type = type(value).__name__

            try:
                parameters = {'key': key, 'value': value, 'updated': updated, 'type': value_type}
                get_database().execute(CacheObject.__table__.insert(), parameters)
            except IntegrityError:
                # when unique constraint kicks in, just try again in which case it
                # should just run "UPDATE" instead of "INSERT"
                get_database().rollback()
                self.set(key, orig_value)
                return

        get_database().commit()


cache = Cache()
