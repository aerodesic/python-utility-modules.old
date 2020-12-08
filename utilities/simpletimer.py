import time

class SimpleTimer():
    def __init__(self, time = 0):
        self._STOPPED = 0
        self._RUNNING = 1
        self._EXPIRED = 2
        if time == 0:
            self.stop()

        else:
            self.start(time)

    def start(self, value):
        self._state = self._RUNNING
        self._cycle = value
        self._target = time.time() + value

    def expired(self):
        self._state = self._EXPIRED

    def stop(self):
        self._state = self._STOPPED

    def remaining(self):
        return self._target - time.time() if self._state == self._RUNNING else 0

    # Return elapsed time since start
    def elapsed(self):
        return time.time() - (self._target - self._cycle)

    def is_expired(self):
        if self._state == self._RUNNING and time.time() >= self._target:
           self._state = self._EXPIRED

        return self._state == self._EXPIRED

    def is_running(self):
        return self._state != self._STOPPED and not self.is_expired()

    def is_stopped(self):
        return self._state == self._STOPPED

    def restart(self):
        if self._state == self._EXPIRED:
            self._target += self._cycle
            self._state = self._RUNNING

