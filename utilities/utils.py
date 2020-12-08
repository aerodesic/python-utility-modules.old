#
# Return user's home directory
#
import os
import dbus


# Return the user's home directory or current directory if not found.
def GetHomeDir():
    try:
        path1 = os.environ["USERHOMEDIR"]
    except:
        path1 = ""

    try:
        path2 = os.environ["HOME"]
    except:
        path2 = ""

    try:
        path3 = os.path.expanduser("~")
    except:
        path3 = ""

    if not os.path.exists(path1):
        if not os.path.exists(path2):
            if not os.path.exists(path3):
                path = os.getcwd()

            else:
                path = path3

        else:
            path = path2

    else:
        path = path1

    return path


# Convert dbus types to internal python types
# Taken from https://www.programcreek.com/python/example/13214/dbus.Array August 16, 2018
# and converted to single-entry / single-exit form.
def DBusUnwrap(val):
    if isinstance(val, dbus.ByteArray):
        val = "".join([str(x) for x in val])

    elif isinstance(val, (dbus.Array, list, tuple)):
        val = [DBusUnwrap(x) for x in val]

    elif isinstance(val, (dbus.Dictionary, dict)):
        val = dict([(DBusUnwrap(x), DBusUnwrap(y)) for x, y in val.items()])

    elif isinstance(val, dbus.ObjectPath) and val.startswith('/org/freedesktop/NetworkManager/'):
        classname = val.split('/')[4]
        classname = {
            'Settings': 'Connection',
            'Devices': 'Device',
        }.get(classname, classname)
        val = globals()[classname](val)

    elif isinstance(val, (dbus.Signature, dbus.String)):
        val = str(val)

    elif isinstance(val, dbus.Boolean):
        val = bool(val)

    elif isinstance(val, (dbus.Int16, dbus.UInt16, dbus.Int32, dbus.UInt32, dbus.Int64, dbus.UInt64)):
        val = int(val)

    elif isinstance(val, dbus.Double):
        val = float(val)

    elif isinstance(val, dbus.Byte):
        val = bytes([int(val)])

    return val

# Wrap item as cannonical structures
def DBusWrap(val):
    if isinstance(val, str):
        val = dbus.String(val)

    elif isinstance(val, (list, tuple)):
        val = dbus.Array([DBusWrap(x) for x in val], signature='v')

    elif isinstance(val, bool):
        val = dbus.Boolean(val)

    elif isinstance(val, int):
        val = dbus.Int64(val)

    elif isinstance(val, float):
        val = dbus.Double(val)

    # Turn 'None' into 'False' to avoid errors
    elif val == None:
        val = dbus.Boolean(False)

    elif isinstance(val, dict):
        val = dbus.Dictionary({ x:DBusWrap(val[x]) for x in val}, signature='sv')

    return val


import functools
def default_kwargs(**default_args):
  def actual_decorator(fn):
    @functools.wraps(fn)
    def g(*args, **kwargs):
      newargs = default_args.copy()
      newargs.update(kwargs)
      return fn(*args, **newargs)
    return g
  return actual_decorator


def splitq(s, delim=' '):
    results = []
    while len(s) != 0:
        d = s.find(delim)
        if d < 0:
            f = s.strip().strip('"').strip("'")
            s = ""
        else:
            q1 = s.find('"')
            q2 = s.find("'")
            q = q1 if q2 < 0 or q1 > q2 else q2

            # print("d %d q %d [%s] done %s" % (d, q, s, results))

            if q < 0 or d < q:
                # Split at d
                f = s[0:d].strip()
                s = s[d+1:]
            else:
                # find closing q quote
                pos = s.find(s[q], q+1)
                if pos > q:
                    # print("pos > q: [%s] strip %s" % (s[q:pos], s[q]))
                    f = s[q:pos+1].strip().strip(s[q])
                    s = s[pos+1:].strip().lstrip(delim)

                else:
                    # print("pos <= q: [%s] strip %s" % (s[q:pos], s[q]))
                    f = s[q:].strip().strip(s[q])
                    s = ""

        results.append(f)

    return results

