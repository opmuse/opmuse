import cherrypy
from sqlalchemy import event
from sqlalchemy.orm.attributes import get_history
from opmuse.ws import ws
from opmuse.library import UserAndAlbum


class DatabaseEvents:
    @staticmethod
    def add(type, entity, id, columns, new_values):
        if hasattr(cherrypy.request, '_database_events'):
            key = (type, entity, id)

            if key in cherrypy.request._database_events:
                for name, value in columns.items():
                    if (name not in cherrypy.request._database_events[key][0] or
                            not cherrypy.request._database_events[key][0][name]):
                        cherrypy.request._database_events[key][0][name] = value

                for name, value in new_values.items():
                    cherrypy.request._database_events[key][1][name] = value
            else:
                cherrypy.request._database_events[key] = (columns, new_values)

    @event.listens_for(UserAndAlbum, "after_insert")
    def after_insert(mapper, conn, object):
        DatabaseEvents.send('insert', object)

    @event.listens_for(UserAndAlbum, "after_update")
    def after_update(mapper, conn, object):
        DatabaseEvents.send('update', object)

    def send(type, object):
        columns = DatabaseEvents.get_columns(object)
        new_values = DatabaseEvents.get_values(object)
        DatabaseEvents.add(type, object.__class__.__name__, object.id, columns, new_values)

    @staticmethod
    def get_values(object):
        values = {}

        for column in object.__table__.columns:
            if column.name == "id":
                continue

            values[column.name] = getattr(object, column.name)

        return values

    @staticmethod
    def get_columns(object):
        columns = {}

        for column in object.__table__.columns:
            if column.name == "id":
                continue

            columns[column.name] = get_history(object, column.name).has_changes()

        return columns


class DatabaseEventsTool(cherrypy.Tool):
    def __init__(self):
        cherrypy.Tool.__init__(self, 'on_start_resource', self.start, priority=10)
        cherrypy.engine.subscribe("database_commit_transaction", self.end)

    def start(self):
        cherrypy.request._database_events = {}

    def end(self):
        _database_events = cherrypy.request._database_events
        cherrypy.request._database_events = None

        for key, values in _database_events.items():
            type, entity, id = key
            columns, new_values = values
            ws.emit('database_events.%s.%s' % (entity.lower(), type), id, columns, new_values)
