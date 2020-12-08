#
# Simple wrapper class for DBUS activity (services and emitters)
#

from threading import Lock
import dbus
import dbus.service
import dbus.glib
from dbus.mainloop.glib import DBusGMainLoop
from gi.repository import GObject as gobject

class DBusObject(dbus.service.Object):
    def __init__(self, busname, servicename, bus):
        self._busname = busname
        self._servicename = servicename
        self._bus = bus
        self._signals_caught = {}
        self._siglock = Lock()

    def _startup(self):
        pass

    def _shutdown(self):
        pass

    def _exception(self, e):
        syslog.syslog("DBusObject exception: %s" % e)

    def run(self):
        DBusGMainLoop(set_as_default=True)

        bus_name = dbus.service.BusName(self._busname, self._bus)
        dbus.service.Object.__init__(self, bus_name, self._servicename)

        self._startup()

        try:
            self._loop = gobject.MainLoop()
            self._loop.run()

        except Exception as e:
            self._exception(e)

        # Release all signals remaining
        for signame in sself._signals_caught:
            self.uncatch_signal(signame)

        self._shutdown()

    def catch_signal(self, signame, action):
        self._siglock.Lock()

        if not callable(action):
            raise DboException("action is not callable for signal %s", signame)

        # Remove signal if currently being caught
        if signame in self._signals_caught:
            self.uncatch_signal(signame)

        self._signals_caught[signame] = {
                    'signame': signame,
                    'action': action,
                    'receiver': self._bus.add_signal_receiver(action, dbus_interface=self._busname, signal_name=signame)
        }

        self._sigLock.Unlock()


    def uncatch_signal(self, signame):
        self._siglock.Lock()

        if signame in self._signals_caught:
            self._bus.remove_signal_receiver(self._signals_caught[signame]['action'], self._signals_caught['receiver'],  dbus_interface=self._busname)

        self._siglock.Unlock()


