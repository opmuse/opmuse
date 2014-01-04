# Copyright 2012-2013 Mattias Fliesberg
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

import queue
import threading
import cherrypy
import logging
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

        if hasattr(func, "bgtask_name"):
            self.name = func.bgtask_name.format(*args)
        else:
            self.name = "%r %r %r" % (func, args, kwargs)

        self.started = None
        self.done = None

    def values(self):
        return self.name, self.priority, self.delay, self.func, self.args, self.kwargs

    def __eq__(self, other):
        return other.priority == self.priority

    def __lt__(self, other):
        return other.priority < self.priority


class BackgroundTaskPlugin(SimplePlugin):
    def __init__(self, bus):
        SimplePlugin.__init__(self, bus)

        self.queue = queue.PriorityQueue()
        self.threads = None
        self.start_threads = 6
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
                debug("Starting bgtask thread #%d" % number)

                thread = threading.Thread(target=self.run, args=(number, ), name='idle')
                thread.item = None
                thread.start()

                self.threads.append(thread)

    start.priority = 90

    def stop(self):
        self._running = "drain"

        log("Draining bgtasks, %d items left." % self.queue.qsize())

        if self.threads:
            for thread in self.threads:
                thread.join()

            self.theads = None

        log("Done draining bgtasks.")

        self._running = False

    stop.priority = 90

    def run(self, number):
        while self._running:
            try:
                try:
                    item = self.queue.get(block=True, timeout=2)
                    name, priority, delay, func, args, kwargs = item.values()
                except queue.Empty:
                    if self._running == "drain":
                        return

                    continue
                else:
                    thread = threading.current_thread()

                    item.started = time.time()

                    thread.item = item
                    thread.name = name

                    self.running += 1

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

                    item.done = time.time()

                    thread.name = 'idle'

                    self.running -= 1

                    thread.item = None

                    self.done.put(item)

                    if self.done.qsize() > 20:
                        self.done.get()
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


class BackgroundTaskTool(cherrypy.Tool):
    def __init__(self):
        cherrypy.Tool.__init__(self, 'on_start_resource',
                               self.bind_background_task, priority=10)

    def bind_background_task(self):
        binds = cherrypy.engine.publish('bind_background_task')
        cherrypy.request.bgtask = binds[0]
