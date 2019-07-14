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

from . import setup_db, teardown_db
from opmuse.security import User, hash_password


class TestSecurity:
    def setup_method(self):
        setup_db(self)

    def teardown_method(self):
        teardown_db(self)

    def test_login(self):
        user = self.session.query(User).filter_by(login="admin").one()

        hashed = hash_password("admin", user.salt)

        assert hashed == user.password

        hashed = hash_password("wrong", user.salt)

        assert hashed != user.password
