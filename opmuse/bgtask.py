# Copyright 2012-2014 Mattias Fliesberg
#
# This file is part of opmuse.
#
# opmuse is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# opmuse is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with opmuse.  If not, see <http://www.gnu.org/licenses/>.

import sys
import queue
import threading
import cherrypy
import logging
import time
from functools import total_ordering
from multiprocessing import cpu_count
from cherrypy.process.plugins import SimplePlugin
from opmuse.database import get_session, database_data
from opmuse.utils import get_pretty_errors, mail_pretty_errors


def debug(msg):
    cherrypy.log.error(msg, context='bgtask', severity=logging.DEBUG)


def log(msg, traceback=False):
    cherrypy.log(msg, context='bgtask', traceback=traceback)


class NonUniqueQueueError(Exception):
    pass


class UniquePriorityQueue(queue.PriorityQueue):
    # don't ask, _init is correct dude
    def _init(self, maxsize):
        queue.PriorityQueue._init(self, maxsize)
        self.keys = set()

    def _put(self, item):
        if not item.unique or item.key not in self.keys:
            if item.unique:
                self.keys.add(item.key)

            queue.PriorityQueue._put(self, item)
        else:
            debug('"%s" is already in the queue.' % item.name)
            raise NonUniqueQueueError('"%s" is already in the queue.' % item.name)

    def done(self, item):
        """
        Mark item as done.

        This needs to be called when a task is done or the queue
        will continue to throw NonUniqueQueueError. Only for unique items though.
        """
        if item.unique:
            self.keys.remove(item.key)


@total_ordering
class QueueItem:
    def __init__(self, priority, unique, func, args, kwargs):
        """
        priority
            priority in queue, higher prio will run before those with lower.
        unique
            if True there can only be one item with this signature in the queue.
        func
            function to run
        args
            positional arguments for func
        kwargs
            keyword arguments for fucn
        """

        self.priority = priority
        self.unique = unique
        self.func = func
        self.args = args
        self.kwargs = kwargs

        if hasattr(func, "bgtask_name"):
            self.name = func.bgtask_name.format(*args)
        else:
            self.name = "%r %r %r" % (func, args, kwargs)

        self.key = (func, tuple(args), tuple(kwargs.items()))

        self.started = None
        self.done = None
        self.error = None

    def fail(self, error):
        self.error = error

    def values(self):
        return self.name, self.priority, self.func, self.args, self.kwargs

    def __eq__(self, other):
        return other.priority == self.priority

    def __lt__(self, other):
        return other.priority < self.priority


class BackgroundTaskPlugin(SimplePlugin):
    def __init__(self, bus):
        SimplePlugin.__init__(self, bus)

        self.queue = UniquePriorityQueue()
        self.threads = None
        self.start_threads = cpu_count() * 2
        self.bus.subscribe("bind_background_task", self.bind_background_task)
        self.running = 0
        self.done = queue.Queue()

    def bind_background_task(self):
        return self

    def start(self):
        self._running = True

        if not self.threads:
            self.threads = []

            for number in range(0, self.start_threads):
                thread = threading.Thread(target=self.run, args=(number, ), name='idle')
                thread.item = None
                thread.start()

                self.threads.append(thread)

    start.priority = 90

    def stop(self):
        # change "stop" to "drain" and all tasks in queue will finish before
        # we shut down, with "stop" only the ones running will be allowed to finish.
        self._running = "stop"

        if self._running == "drain":
            log("Draining bgtasks, %d items in queue, %d running." % (self.queue.qsize(), self.running))
        elif self._running == "stop":
            log("Stopping bgtasks, %d running left, aborting %d in queue." % (self.running, self.queue.qsize()))

        if self.threads:
            for thread in self.threads:
                thread.join()

            self.theads = None

        if self._running == "drain":
            log("Done draining bgtasks.")
        elif self._running == "stop":
            log("Done stopping bgtasks.")

        self._running = False

    stop.priority = 90

    def run(self, number):
        debug("Starting bgtask thread #%d" % number)

        while self._running:
            if self._running == "stop":
                break

            item = None

            try:
                try:
                    item = self.queue.get(block=True, timeout=2)
                    name, priority, func, args, kwargs = item.values()
                except queue.Empty:
                    if self._running == "drain":
                        break

                    continue
                else:
                    thread = threading.current_thread()

                    item.started = time.time()

                    thread.item = item
                    thread.name = name

                    self.running += 1

                    debug("Running bgtask in thread #%d %r with priority %d, args %r and kwargs %r." %
                          (number, func, priority, args, kwargs))

                    database_data.database = get_session()

                    func(*args, **kwargs)

                    try:
                        database_data.database.commit()
                    except:
                        database_data.database.rollback()
                        raise
            except Exception as error:
                log("Error in bgtask thread #%d %r, args %r and kwargs %r." %
                    (number, func, args, kwargs), traceback=True)

                item.fail(error)

                name, text, html = get_pretty_errors(sys.exc_info())

                name = "bgtask %r: %s" % (func, name)

                mail_pretty_errors(name, text, html)
            finally:
                if item is not None:
                    database_data.database.remove()
                    database_data.database = None

                    self.queue.task_done()
                    self.queue.done(item)

                    item.done = time.time()

                    thread.name = 'idle'

                    thread.item = None

                    self.done.put(item)

                    # store max 50 items in done queue
                    if self.done.qsize() > 50:
                        self.done.get()

                    self.running -= 1

        debug("Stopping bgtask thread #%d" % number)

    def put_unique(self, func, priority, *args, **kwargs):
        """
            Add task to queue and throw error if there's already an item with the
            same signature as this in the queue. Higher priority means it will
            run before those with lower.
        """
        self.queue.put(QueueItem(priority, True, func, args, kwargs))

    def put(self, func, priority, *args, **kwargs):
        """
            Add task to queue. Higher priority means it will run before those with lower.
        """
        self.queue.put(QueueItem(priority, False, func, args, kwargs))


class BackgroundTaskTool(cherrypy.Tool):
    def __init__(self):
        cherrypy.Tool.__init__(self, 'on_start_resource',
                               self.bind_background_task, priority=10)

    def bind_background_task(self):
        binds = cherrypy.engine.publish('bind_background_task')
        cherrypy.request.bgtask = binds[0]
