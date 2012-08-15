import string
import random
from opmuse.boot import configure
from opmuse.database import get_raw_session
from opmuse.who import User, hash_password

configure()

database = get_raw_session()

# begin fixtures

salt = ''.join(random.choice(string.ascii_letters + string.digits) for i in range(64))
user = User('admin', hash_password("admin", salt), salt)
database.add(user)

# end fixtures

database.commit()
