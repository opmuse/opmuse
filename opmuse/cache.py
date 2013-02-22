import time
import json
from sqlalchemy.orm import deferred
from sqlalchemy import Column, Integer, String, BLOB, BigInteger, func
from sqlalchemy.dialects import mysql
from sqlalchemy.orm.exc import NoResultFound
from opmuse.database import Base, get_session


class CacheObject(Base):
    __tablename__ = 'cache_objects'

    id = Column(Integer, primary_key=True)
    key = Column(String(128), index=True, unique=True)
    type = Column(String(128))
    updated = Column(BigInteger, index=True)
    value = deferred(Column(BLOB().with_variant(mysql.LONGBLOB(), 'mysql')))


class Cache:
    def __init__(self, session):
        self.session = session

    def needs_update(self, key, age = 3600):
        now = int(time.time())

        count = (self.session.query(func.count(CacheObject.id))
                 .filter(CacheObject.key == key).scalar())

        if count > 0:
            count = (self.session.query(func.count(CacheObject.id))
                     .filter(CacheObject.key == key).filter("(%d - updated) > %d" % (now, age)).scalar())

            return count > 0
        else:
            return True

    def get(self, key):
        try:
            object = self.session.query(CacheObject).filter(CacheObject.key == key).one()

            if object.type == 'str':
                return object.value.decode()
            elif object.type == 'dict' or object.type == 'list':
                return json.loads(object.value.decode())

            return object.value
        except NoResultFound:
            pass

    def set(self, key, value):
        if not isinstance(value, (str, bytes, dict, list)):
            raise ValueError("Unsupported value type.")

        count = (self.session.query(func.count(CacheObject.id))
                 .filter(CacheObject.key == key).scalar())

        updated = int(time.time())

        value_type = type(value).__name__

        if value_type == 'str':
            value = value.encode()
        elif value_type == 'dict' or value_type == 'list':
            value = json.dumps(value).encode()

        if count > 0:
            (self.session.query(CacheObject)
                .filter(CacheObject.key == key)
                .update({'value': value, 'updated': updated, 'type': value_type}))
        else:
            self.session.execute(CacheObject.__table__.insert(),
                                 {'key': key, 'value': value, 'updated': updated, 'type': value_type})

        self.session.commit()
