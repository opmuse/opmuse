import queue
import threading
import cherrypy
import logging
import inspect
import time
from functools import total_ordering
from cherrypy.process.plugins import SimplePlugin
from opmuse.database import get_session


def debug(msg):
    cherrypy.log.error(msg, context='bgtask', severity=logging.DEBUG)


def log(msg, traceback=False):
    cherrypy.log(msg, context='bgtask', traceback=traceback)


bgtask_data = threading.local()


@total_ordering
class QueueItem:
    def __init__(self, priority, delay, func, args, kwargs):
        self.priority = priority
        self.delay = delay
        self.func = func
        self.args = args
        self.kwargs = kwargs

    def values(self):
        return self.priority, self.delay, self.func, self.args, self.kwargs

    def __eq__(self, other):
        return other.priority == self.priority

    def __lt__(self, other):
        return other.priority < self.priority


class BackgroundTaskQueue(SimplePlugin):
    def __init__(self, bus):
        SimplePlugin.__init__(self, bus)

        self.queue = queue.PriorityQueue()
        self.threads = None
        self.start_threads = 6

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

        log("Draining bgtasks, %d items left." % self.queue.qsize())

        if self.threads:
            for thread in self.threads:
                thread.join()

            self.theads = None

        log("Done draining bgtasks.")

        self.running = False

    stop.priority = 90

    def run(self, number):
        while self.running:
            try:
                try:
                    priority, delay, func, args, kwargs = self.queue.get(block=True, timeout=2).values()
                except queue.Empty:
                    if self.running == "drain":
                        return

                    continue
                else:
                    if delay is not None:
                        debug("Delaying bgtask for %ds in thread #%d %r with priority %d, args %r and kwargs %r." %
                              (delay, number, func, priority, args, kwargs))

                        time.sleep(delay)

                    debug("Running bgtask in thread #%d %r with priority %d, args %r and kwargs %r." %
                          (number, func, priority, args, kwargs))

                    bgtask_data.database = get_session()

                    func(*args, **kwargs)

                    try:
                        bgtask_data.database.commit()
                    except:
                        bgtask_data.database.rollback()
                        raise
                    finally:
                        bgtask_data.database.remove()
                        bgtask_data.database = None

                    self.queue.task_done()
            except:
                log("Error in bgtask thread #%d %r." % (number, self), traceback=True)

    def put(self, func, priority, *args, **kwargs):
        """
            Add task to queue, higher priority means it will run before those with lower.
        """
        self.queue.put(QueueItem(priority, None, func, args, kwargs))

    def put_delay(self, func, priority, delay, *args, **kwargs):
        """
            Like put() but takes an extra "delay" argument which specifies a delay in seconds
            for this task.
        """
        self.queue.put(QueueItem(priority, delay, func, args, kwargs))
