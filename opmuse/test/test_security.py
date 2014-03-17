from . import setup_db, teardown_db
from nose.tools import with_setup
from opmuse.security import User, hash_password


@with_setup(setup_db, teardown_db)
class TestSecurity:
    def test_login(self):
        user = self.session.query(User).filter_by(login="admin").one()

        hashed = hash_password("admin", user.salt)

        assert hashed == user.password

        hashed = hash_password("wrong", user.salt)

        assert hashed != user.password
