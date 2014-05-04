import cherrypy
import socketserver
from cherrypy.process.plugins import SimplePlugin


def log(msg):
    cherrypy.log(msg, context='mpd')


class MpdCommands:
    @staticmethod
    def currentsong():
        return (b"file: http://op.inty.se/play/stream?auth_tkt=cf3bd1ca28686d7f0211d815a717b3e6534c46e4inty!\n" +
            b"Artist: Totalt Javla Morker\n" +
            b"Title: Livet ar Ett Lungemfysem\n" +
            b"Album: Manniskans Ringa Varde\n" +
            b"Track: 14\n" +
            b"Genre: Crust\n" +
            b"Pos: 0\n" +
            b"Id: 1\n")

    @staticmethod
    def status():
        return (b"volume: 30\n" +
            b"repeat: 0\n" +
            b"random: 0\n" +
            b"single: 0\n" +
            b"consume: 0\n" +
            b"playlist: 1\n" +
            b"playlistlength: 0\n" +
            b"mixrampdb: 0.000000\n" +
            b"state: stop\n")


class MpdRequestHandler(socketserver.StreamRequestHandler):
    def __init__(self, *args, **kwargs):
        socketserver.StreamRequestHandler.__init__(self, *args, **kwargs)

    def handle(self):
        welcome = b"OK MPD 0.18.0\n"

        self.request.send(welcome)

        commands = []

        command_list_begin = False
        command_list_ok_begin = False

        while True:
            try:
                self.data = self.rfile.readline().strip()

                if len(self.data) == 0:
                    raise IOError

                print(self.data)

                if self.data == b"command_list_ok_begin":
                    command_list_begin = True
                    command_list_ok_begin = True
                    continue

                if self.data == b"command_list_begin":
                    command_list_begin = True
                    continue

                if self.data != b"command_list_end" and command_list_begin:
                    commands.append(self.data)
                    continue
                elif not command_list_begin:
                    commands.append(self.data)

                for command in commands:
                    print('command')

                    if command == b"status":
                        self.request.send(MpdCommands.status())
                    elif command == b"currentsong":
                        self.request.send(MpdCommands.currentsong())

                    if command_list_ok_begin:
                        self.request.send(b'list_OK\n')

                self.request.send(b'OK\n')

                print('end')

                break
            except IOError:
                break


class MpdServer(socketserver.TCPServer, socketserver.ThreadingMixIn):
    def __init__(self, host, port):
        socketserver.TCPServer.__init__(self, (host, port), MpdRequestHandler)


class MpdServerPlugin(SimplePlugin):
    def __init__(self, bus):
        SimplePlugin.__init__(self, bus)

        self.server = None

    def start(self):
        #config = cherrypy.tree.apps[''].config['opmuse']
        self.server = MpdServer("localhost", 6611)
        log("Starting MPD server.")
        self.server.serve_forever(poll_interval=.5)

    start.priority = 140

    def stop(self):
        if self.server is not None:
            log("Stopping MPD server.")
            self.server.shutdown()
