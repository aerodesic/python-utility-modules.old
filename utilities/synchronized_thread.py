# -*- coding: utf-8 -*-
from threading import Thread, Lock, current_thread, Timer
import queue
import time
# import traceback
import syslog

_thread_objects_lock = Lock()
_thread_objects = {}

#
# Send a message to a thread:
#  <message> is the contents (a dictionary)
#  <to> is the destination thread name
#  <reply> if True, tacks on a 'reply_to' dictionary item and send waits for <timeout> seconds before Empty exception
#  if <reply> is a string, then the reply message will be delivered to the <reply> thread name with the <reply_token>
#  placed at the first element of a tuple, formed by [ <reply_token> <reply message> ]
# <reply_token) is only used if <reply> is a string and is used to build the reply message to the <reply> thread.
#
def send_message(message, to=None, reply=False, timeout=None, reply_token='reply'):
    results = None

    # print ("send_message from '%s' to '%s' %s (reply %s timeout %s)" % (current_thread().name, to, message, reply, timeout))

    try:
        if not isinstance(message, (list, tuple)):
            results = "%s: Invalid message format %s to %s" % (message, to, current_thread().name)
            syslog.syslog(results)

        else:
            packet = { 'data': message, 'from': current_thread().name }

            if to == None:
                # Send to all
                _thread_objects_lock.acquire()

                for name in _thread_objects:
                    thread = _thread_objects[name]
                    thread._queue.put(packet)

                _thread_objects_lock.release()

            else:
                if reply == True:
                    # Reply to local queue and block for results
                    reply_queue = queue.Queue()
                    packet['reply_to'] = reply_queue

                elif isinstance(reply, str):
                    # Reply back to another thread
                    packet['reply_to'] = reply
                    packet['reply_token'] = reply_token

                _thread_objects_lock.acquire()

                if to in _thread_objects:
                    _thread_objects[to]._queue.put(packet)
                else:
                    syslog.syslog("Thread '%s' not in _thread_objects" % to)

                _thread_objects_lock.release()

                if reply == True:
                    results = reply_queue.get(timeout=timeout)

    except Exception as e:
        syslog.syslog("send_message exception '%s' (%s)" % (str(e), type(e)))
        # traceback.print_exc()
        results = { 'error': str(e) }

    return results

# Interface for synchronized thread with command queue
class SynchronizedThreadWithQueue(Thread):
    # Internal object used to send termination request
    class _ExitObject():
        pass

    def __init__(self, name, parent=None, app=None, queue_blocking=True, queue_timeout=None, max_queue=0):
        super(SynchronizedThreadWithQueue, self).__init__(name=name)

        self._running = True
        self._queue = queue.Queue(max_queue)
        self._parent = parent
        self._app = app
        self._queue_blocking = queue_blocking
        self._queue_timeout = queue_timeout

        self._ready_signal = Lock()
        self._ready_signal.acquire()
        self._sync_signal = Lock()
        self._sync_signal.acquire()

        self._exit_object = self._ExitObject()
        self._timers = {}

        # print("%s constructor, parent '%s'" % (self.name, parent.name if parent else "None"))

        # Add thread to global thread objects for message passing
        _thread_objects_lock.acquire()

        if name in _thread_objects:
            syslog.syslog("%s: !!!! already in _thread_objects" % name)
        else:
            # print("Adding '%s' to _thread_objects" % name)
            _thread_objects[name] = self

        _thread_objects_lock.release()

    def get_app(self):
        return self._app

    def get_parent(self):
        return self._parent

    def wait_ready(self):
        syslog.syslog("Waiting for %s to intialize" % self.name)
        self._ready_signal.acquire()
        syslog.syslog("%s initialized" % self.name)

    def signal_sync(self):
        syslog.syslog("Release %s to run" % self.name)
        self._sync_signal.release()

    # Put message in local queue
    def put(self, message):
        self._queue.put({'data': message})

    def stop(self, join=True):
        syslog.syslog("Stopping %s thread" % self.name)
        self._queue.put(self._exit_object)
        if join:
            self.join()

    # No access to 'varstore' is valid before the threads are intiailized.
    # The calls to add_varstore_schema must occur before the main thread creates the varstore.
    def add_varstore_schema(self, schema):
        pass

    # Dummy in case not supplied by derived class
    def initialize(self):
        pass

    def started(self):
        pass

    # Only subordinate blockable actions allowed in shutdown
    def shutdown(self):
        pass

    # Dummy in case not supplied by derived class
    def message(self, message, from_thread):
        syslog.syslog("No message handler in %s for %s from %s" % (self._name, message, from_thread))

    def _timer_fired(self, name, value):
        # print("_timer_fired in '%s' name '%s' with '%s'" % (self.name, name, value))
        # Send local message to self.
        self.put([ name, value ])
        del(self._timers[name])

    def set_timer(self, name, time, value=None):
        # Remove any extant by this name
        self.kill_timer(name)

        # print("set_timer in '%s' name '%s' for %s with '%s'" % (self.name, name, time, value))

        # Construct timer element with parameters passed from caller
        self._timers[name] = Timer(time, self._timer_fired, kwargs={'name':name, 'value':value})

        # Start the timer
        self._timers[name].start()

    def kill_timer(self, name):
        # print("Killing timer '%s'" % name)
        # If timer is extant in table, kill it
        if name in self._timers:
            self._timers[name].cancel()
            del(self._timers[name])

    def run(self):
        syslog.syslog("%s initializing" % self.name)

        self.initialize()

        self._ready_signal.release()
        self._sync_signal.acquire()


        syslog.syslog("%s: blocking %s timeout %s" % (self.name, self._queue_blocking, self._queue_timeout))

        self.started()

        while self._running:

            try:
                message = self._queue.get(block=self._queue_blocking, timeout=self._queue_timeout)

                if message == self._exit_object:
                    self._running = False

                else:
                    # print("SynchronizedThreadWithQueue(%s) processing %s" % (self.name, message))
                    # message contains a 'data' and optional 'reply_to' queue.
                    results = self.message(message['data'], message['from'] if 'from' in message else None)

                    if 'reply_to' in message:
                        reply_to = message['reply_to']
                        if isinstance(reply_to, queue.Queue):
                            # Put into the the sender's reply queue
                            reply_to.put(results)

                        elif isinstance(reply_to, str):
                            # Send reply to input queue of another thread
                            _thread_objects_lock.acquire()

                            if reply_to in _thread_objects:
                                # Send as if directed to this thread.  This allows a 'response' to a command to be delivered
                                # asynchronously as if it was another command.
                                _thread_objects[reply_to]._queue.put({ 'data': [ message['reply_token'], results ], 'from': self._name })

                            else:
                                syslog.syslog("Thread '%s' not in _thread_objects" % reply_to)

                            _thread_objects_lock.release()

                    elif results != None:
                        syslog.syslog("%s: Results from %s is %s" % (self.name, message, results))

            except queue.Empty:
                # Turn timeout into empty
                self.message(None, None)


        self.shutdown()

        # Remove timers
        for timer in [ x for x in self._timers] :
            # print("delete timer %s" % timer)
            self._timers[timer].cancel()
            del(self._timers[timer])

        # Remove thread from global _thread_objects
        syslog.syslog("Removing thread %s from thread_objects" % self.name)
        _thread_objects_lock.acquire()
        if self.name in _thread_objects:
            del(_thread_objects[self.name])

        else:
            syslog.syslog("%s: !!! %s not in _thread_objects" % self.name)
        _thread_objects_lock.release()

        syslog.syslog("%s exiting" % self.name)

