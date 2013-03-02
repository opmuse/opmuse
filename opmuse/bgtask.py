import queue
import threading
import cherrypy
import logging
from cherrypy.process.plugins import SimplePlugin


def debug(msg):
    cherrypy.log.error(msg, context='bgtask', severity=logging.DEBUG)


def log(msg):
    cherrypy.log(msg, context='bgtask')


class BackgroundTaskQueue(SimplePlugin):
    def __init__(self, bus):
        SimplePlugin.__init__(self, bus)

        self.tasks = queue.Queue()
        self.thread = None

    def start(self):
        self.running = True

        if not self.thread:
            self.thread = threading.Thread(target=self.run)
            self.thread.start()

    start.priority = 90

    def stop(self):
        self.running = "draining"

        if self.thread:
            self.thread.join()
            self.thread = None

        self.running = False

    def run(self):
        while self.running:
            try:
                try:
                    func, args, kwargs = self.tasks.get(block=True, timeout=2)
                except queue.Empty:
                    if self.running == "draining":
                        return

                    continue
                else:
                    debug("Running bgtask %r with args %r and kwargs %r." % (func, args, kwargs))

                    func(*args, **kwargs)

                    self.tasks.task_done()
            except:
                log("Error in bgtask %r." % self, level=40, traceback=True)

    def put(self, func, *args, **kwargs):
        self.tasks.put((func, args, kwargs))


