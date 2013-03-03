import queue
import threading
import cherrypy
import logging
import inspect
from cherrypy.process.plugins import SimplePlugin
from opmuse.database import get_session


def debug(msg):
    cherrypy.log.error(msg, context='bgtask', severity=logging.DEBUG)


def log(msg):
    cherrypy.log(msg, context='bgtask')


class BackgroundTaskQueue(SimplePlugin):
    def __init__(self, bus):
        SimplePlugin.__init__(self, bus)

        self.tasks = queue.Queue()
        self.threads = None
        self.start_threads = 4

    def start(self):
        self.running = True

        if not self.threads:
            self.threads = []

            for number in range(0, self.start_threads):
                debug("Starting bgtask thread #%d" % number)

                thread = threading.Thread(target=self.run, args=(number, ))
                thread.start()

                self.threads.append(thread)

    start.priority = 90

    def stop(self):
        self.running = "drain"

        if self.threads:
            for thread in self.threads:
                thread.join()

            self.theads = None

        self.running = False

    def run(self, number):
        database = get_session()

        while self.running:
            try:
                try:
                    func, args, kwargs = self.tasks.get(block=True, timeout=2)
                except queue.Empty:
                    if self.running == "drain":
                        return

                    continue
                else:
                    debug("Running bgtask in thread #%d %r with args %r and kwargs %r." %
                          (number, func, args, kwargs))

                    argspec = inspect.getfullargspec(func)

                    if '_database' in argspec.args:
                        kwargs['_database'] = database

                    func(*args, **kwargs)

                    self.tasks.task_done()
            except:
                log("Error in bgtask thread #%d %r." % (number, self), level=40, traceback=True)

    def put(self, func, *args, **kwargs):
        self.tasks.put((func, args, kwargs))


