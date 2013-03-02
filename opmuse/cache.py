import time
import json
from sqlalchemy.orm import deferred
from sqlalchemy import Column, Integer, String, BLOB, BigInteger, func
from sqlalchemy.dialects import mysql
from sqlalchemy.orm.exc import NoResultFound
from opmuse.database import Base


class CacheObject(Base):
    __tablename__ = 'cache_objects'

    id = Column(Integer, primary_key=True)
    key = Column(String(128), index=True, unique=True)
    type = Column(String(128))
    updated = Column(BigInteger, index=True)
    value = deferred(Column(BLOB().with_variant(mysql.LONGBLOB(), 'mysql')))


class Cache:
    def needs_update(self, key, age, database):
        now = int(time.time())

        count = (database.query(func.count(CacheObject.id))
                 .filter(CacheObject.key == key).scalar())

        if count > 0:
            count = (database.query(func.count(CacheObject.id))
                     .filter(CacheObject.key == key).filter("(%d - updated) > %d" % (now, age)).scalar())

            return count > 0
        else:
            return True

    def get(self, key, database):
        try:
            object = database.query(CacheObject).filter(CacheObject.key == key).one()

            if object.type == 'str':
                return object.value.decode()
            elif object.type == 'dict' or object.type == 'list':
                return json.loads(object.value.decode())

            return object.value
        except NoResultFound:
            pass

    def set(self, key, value, database):
        if value is not None and not isinstance(value, (str, bytes, dict, list)):
            raise ValueError("Unsupported value type.")

        count = (database.query(func.count(CacheObject.id))
                 .filter(CacheObject.key == key).scalar())

        updated = int(time.time())

        value_type = type(value).__name__

        if value_type == 'str':
            value = value.encode()
        elif value_type == 'dict' or value_type == 'list':
            value = json.dumps(value).encode()

        if count > 0:
            (database.query(CacheObject)
                .filter(CacheObject.key == key)
                .update({'value': value, 'updated': updated, 'type': value_type}))
        else:
            database.execute(CacheObject.__table__.insert(),
                                 {'key': key, 'value': value, 'updated': updated, 'type': value_type})

        database.commit()


cache = Cache()
