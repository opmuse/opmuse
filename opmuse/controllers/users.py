import cherrypy
from sqlalchemy.orm.exc import NoResultFound
from opmuse.database import get_database
from opmuse.security import User, Role
from opmuse.remotes import remotes


class Users:
    @cherrypy.expose
    @cherrypy.tools.authenticated(needs_auth=True)
    @cherrypy.tools.jinja(filename='users/index.html')
    def default(self, *args):
        if len(args) == 1:
            raise cherrypy.InternalRedirect('/users/user/%s' % args[0])

        roles = (get_database().query(Role).order_by(Role.name).all())
        users = (get_database().query(User).order_by(User.login).all())

        for user in users:
            remotes.update_user(user)

        return {
            'users': users,
            'roles': roles
        }

    @cherrypy.expose
    @cherrypy.tools.authenticated(needs_auth=True)
    @cherrypy.tools.jinja(filename='users/user.html')
    def user(self, login):
        try:
            user = (get_database().query(User)
                    .filter_by(login=login)
                    .order_by(User.login).one())
        except NoResultFound:
            raise cherrypy.NotFound()

        remotes.update_user(user)
        remotes_user = remotes.get_user(user)

        return {
            'user': user,
            'remotes_user': remotes_user
        }
