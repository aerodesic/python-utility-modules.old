This module contains some miscellaneous support utilities:

synchronized_thread.py:
  SynchronizedThreadWithQueue -
    A thread with start and shutdown synchronization plus containing a message queue for
    inter-thread communication.  In companion with the 'send_message' global function,
    threads can send messages to any other thread by name and optionally receive a reply
    from THAT thread only.

    synchronized threads do not have a run() method, but rather a message() method that is
    called when a message is received.  The the caller of the send_message requests an
    answer, the return value from message() is passed back to the caller as the return
    value.

configuration.py:
    Configuration class the wraps a configuration database, serialized with a JSON backing
    store.  The configuration entity is defined with a Python dict 'schema' that provides
    the invariat parts of the database, plus initial default values.  The actual values
    are serialized to a (user supplied pathname) file where only the actual names and values
    are stored.

delmodule.py:
   Provides a global method for deleting a module that was previously inherited.

poly.py:
   A simple polynomial computation class.

simpletimer.py:
   A simple timer that has no OS components other than testing for elapsed time.  Functions
   to not block, but are rather used by period tests to see if times specified have elapsed
   or if timers have been reset or cancelled.

utils.py:
   A mix of some general purpose utility functions:
     GetHomeDir()  - returns the home directory of the current user based upon several
     environment variable probes.

   DbusWrap / DBusUnwrap - wrap and unwrap utilities for 'variant' objects passed through
   DBus methods.

   default_kwargs()  A decorator that provides specification of default kwargs for
   functions.

   splitq()  A function to split a string by a delimiter (default ' ') with recognition of
   strings bounded by '' and "".  Uses no other libraries - just brute force string scanning.

