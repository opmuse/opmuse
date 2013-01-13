import json
import cherrypy


class Messages:

    def warning(self, text):
        self.publish('warning', text)

    def success(self, text):
        self.publish('success', text)

    def publish(self, type, text):
        cherrypy.response.headers['X-Opmuse-Message'] = json.dumps({
            'type': type,
            'text': text
        })

messages = Messages()
