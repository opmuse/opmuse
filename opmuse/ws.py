import json
import cherrypy
from ws4py.server.cherrypyserver import WebSocketPlugin, WebSocketTool
from ws4py.websocket import WebSocket


def log(msg):
    cherrypy.log(msg, context='ws')


class WebSocketHandler(WebSocket):
    def auth_user(self, user):
        self.user = {
            'id': user.id,
            'login': user.login
        }

    def opened(self):
        ws.auth_user(self)

    def received_message(self, message):
        data = json.loads(message.data.decode('utf8'))
        ws.receive(data['event'], data['args'], self)

    def closed(self, code, reason=None):
        ws.cleanup(self)


class WsUser:
    def __init__(self, id, login):
        self.id = id
        self.login = login
        self.handlers = []
        self._data = {}

    def set(self, key, value):
        self._data[key] = value

    def get(self, key):
        if key in self._data:
            return self._data[key]

    def add_handler(self, handler):
        self.handlers.append(handler)

    def remove_handler(self, handler):
        self.handlers.remove(handler)

    def emit(self, message):
        for handler in self.handlers:
            WsUser.send(message, handler)

    @staticmethod
    def send(message, handler):
        try:
            handler.send(json.dumps(message))
        except Exception as error:
            log('Error occured while sending: %s' % error)


class Ws:
    def __init__(self):
        self._all_handlers = []
        self._ws_users = {}
        self._events = {}

    def get_ws_user_by_handler(self, handler):
        return self.get_ws_user(handler.user['id'], handler.user['login'])

    def get_ws_user(self, id = None, login = None):
        if id is None:
            id = cherrypy.request.user.id

        if login is None:
            login = cherrypy.request.user.login

        if id not in self._ws_users:
            self._ws_users[id] = WsUser(id, login)

        return self._ws_users[id]

    def auth_user(self, handler):
        ws_user = self.get_ws_user_by_handler(handler)
        ws_user.add_handler(handler)

        self._all_handlers.append(handler)

    def cleanup(self, handler):
        if handler.user['id'] in self._ws_users:
            self._ws_users[handler.user['id']].remove_handler(handler)

        self._all_handlers.remove(handler)

    def emit(self, event, *args, handler = None, ws_user = None):
        if handler is not None:
            if not isinstance(handler, list):
                handlers = [handler]
            else:
                handlers = handler

            for handler in handlers:
                WsUser.send({
                    'event': event,
                    'args': args
                }, handler)
        else:
            if ws_user is None:
                user = cherrypy.request.user

                if user.id in self._ws_users:
                    ws_user = self._ws_users[user.id]

            if ws_user is not None:
                ws_user.emit({
                    'event': event,
                    'args': args
                })

    def emit_all(self, event, *args):
        self.emit(event, *args, handler = self._all_handlers)

    def receive(self, event, args, handler):
        ws_user = self.get_ws_user_by_handler(handler)
        if event in self._events:
            for callback in self._events[event]:
                callback(*args, ws_user = ws_user)

    def on(self, event, callback):
        if event not in self._events:
            self._events[event] = []

        self._events[event].append(callback)


class WsController(object):
    @cherrypy.expose
    def default(self, *args, **kwargs):
        cherrypy.request.ws_handler.auth_user(cherrypy.request.user)


ws = Ws()
