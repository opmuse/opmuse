# Copyright 2012-2014 Mattias Fliesberg
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

import string
import random
from opmuse.database import get_raw_session
from opmuse.security import User, Role, hash_password


def run_fixtures():
    database = get_raw_session()

    # begin fixtures

    salt = ''.join(random.choice(string.ascii_letters + string.digits) for i in range(64))
    admin_user = User('admin', hash_password("admin", salt), 'admin@example.com', salt)

    salt = ''.join(random.choice(string.ascii_letters + string.digits) for i in range(64))
    user_user = User('user', hash_password("user", salt), 'user@example.com', salt)

    database.add(admin_user)
    database.add(user_user)

    admin_role = Role('admin')

    database.add(admin_role)

    admin_role.users.append(admin_user)

    # end fixtures

    database.commit()
