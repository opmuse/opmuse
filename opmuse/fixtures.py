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
