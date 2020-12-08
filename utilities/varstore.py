#
# Varstore class
#

import os
from threading import Lock
import json
from copy import deepcopy
from aoutils.utils import default_kwargs, splitq

# A varstore item is a tuple containing:
#  "<varname>": { "desc": <description>, [ "fmt": <display format>, ] "value": <value>, [ "visible" : <boolean>, ] }
# Lacking "visible", item is assumed to be visible.
# lacking fmt, format is assumed to be <string>
#
# When written to storage, a simplified table is stored:
#
# { "var name": <value>, ... }
#
# And remerged into this table upon reload
#
# This table is the default values (and schema) for this varstore information
#

# If a varstore entry has a 'protection' value that is less than this, it
# cannot be overwritten by default.
DEFAULT_PROTECTION = 1
NO_PROTECTION = 0

class VarstoreException(Exception):
    def __init__(self, msg):
        super(VarstoreException, self).__init__(msg)
        self._msg = msg

    def __str__(self):
        return self._msg

class VarstoreExceptionFile(VarstoreException):
    def __init__(self, msg, filename):
        super(VarstoreExceptionFile, self).__init__(msg)
        self._filename = filename

    def __str__(self):
        return "%s: '%s'" % (self._msg, self._filename)

class VarstoreExceptionUndefinedVar(VarstoreException):
    def __init__(self, varname):
        super(VarstoreExceptionUndefinedVar, self).__init__("Undefined var")
        self._varname = varname

    def __str__(self):
        return "%s: '%s'" % (self._msg, self._varname)

class VarstoreExceptionProtectedVar(VarstoreException):
    def __init__(self, varname, extra=None):
        super(VarstoreExceptionProtectedVar, self).__init__("Protected var")
        self._varname = varname

    def __str__(self):
        return "%s: '%s'" % (self._msg, self._varname)

class VarstoreExceptionAccessError(VarstoreException):
    def __init__(self, varname, extra=None):
        super(VarstoreExceptionAccessError, self).__init__("Access error")
        self._varname = varname
        self._extra = extra

    def __str__(self):
        if self._extra:
            return "%s: '%s' (%s)" % (self._msg, self._varname, self._extra)
        else:
            return "%s: '%s'" % (self._msg, self._varname)

class VarstoreExceptionOption(VarstoreException):
    def __init__(self, varname, value):
        super(VarstoreExceptionOption, self).__init__("%s not an option" % value)
        self._varname = varname

    def __str__(self):
        return "%s: '%s'" % (self._msg, self._varname)


class VarstoreExceptionRange(VarstoreException):
    def __init__(self, varname, value, range):
        super(VarstoreExceptionRange, self).__init__("%s not in range [%s .. %s]" % (value, range[0], range[1]))
        self._varname = varname

    def __str__(self):
        return "%s: '%s'" % (self._varname, self._msg)

class Varstore():
    def __init__(self, schema=None, filename=None, propagate=None):
        self._lock = Lock()
        self._store = deepcopy(schema)
        self._filename = filename
        self._propagate = propagate
        self._loaded = False

    def AddSchema(self, schema):
        if isinstance(schema, dict):
            for key in schema:
                self._store[key] = deepcopy(schema[key])

    @default_kwargs(propagate=True)
    def Load(self, filename = None, **kwargs):
        if not self._loaded:
            self._lock.acquire()

            try:
                if filename is None:
                    filename = self._filename

                try:
                    f = open(filename, "r")
                    store = json.load(f)
                    self._mergeVarstore(self._store, store, protection=NO_PROTECTION)

                except Exception as e:
                    raise VarstoreExceptionFile("Unable to read file", filename)

                finally:
                    f.close()

                if kwargs['propagate']:
                    self.Propagate()

            except:
                raise VarstoreExceptionFile("Unable to open file", filename)

            finally:
                self._lock.release()

            self._loaded = True

    @default_kwargs(filename=None, propagate=True, callables=False, ignore_protected=True, not_saved=False)
    def Save(self, **kwargs):
        filename = kwargs['filename'] if 'filename' in kwargs else None

        self._lock.acquire()

        try:
            # print("Save: callables %s" % kwargs['callables'])
            # Create the truncated varstore value
            varstore_data = self._valuesOf(self._store, **kwargs)

            if filename is None:
                filename = self._filename

            if filename:
                # print("varstore Save on '%s'" % filename)
                if not os.access(filename, os.F_OK):
                    # Try to create subdirs
                    dirname = os.path.dirname(filename)
                    if dirname:
                        if not os.path.isdir(dirname):
                            os.makedirs(dirname)

                f = open(filename, "w")
                f.write(json.dumps(varstore_data, indent=3, sort_keys=True) + "\n")
                f.close()

            # Propagate store if requested
            if kwargs['propagate']:
                self.Propagate()

        except Exception as e:
            raise VarstoreExceptionFile(str(e), filename)

        finally:
            self._lock.release()

    # Export all (including callables) to caller.
    @default_kwargs(protection=DEFAULT_PROTECTION, callables=False)
    def Export(self, **kwargs):
        self._lock.acquire()
        varstore_data = self._valuesOf(self._store, **kwargs)
        self._lock.release()
        return varstore_data

    def Propagate(self):
        if self._propagate is not None:
            # Propagate all values
            self._propagate(self._valuesOf(self._store, protection=NO_PROTECTION))

    @default_kwargs(protection=DEFAULT_PROTECTION)
    def Get(self, var, **kwargs):
        (saved, var_location) = self._findVar(var, self._store, **kwargs)

        # Get the (resolved callable) value
        value =  self._get_var_value(var_location, var, **kwargs)

        # Resolve any dict items
        return self._valuesOf(value, **kwargs)

    @default_kwargs(propagate=False, protection=DEFAULT_PROTECTION, readonly_check=True)
    def Set(self, var, value, **kwargs):
        # Locate the var body (the cell containing the 'value' and attributes and return
        # the aggregate 'saved'.
        (saved, var_location) = self._findVar(var, self._store, **kwargs)

        # print ("Set: saved %s var_location %s" % (saved, var_location))
        # print ("     value %s" % value)

        if isinstance(value, dict):
            # Do this with an Apply
            self.Apply(value, var=var, **kwargs)

        elif self._set_var_value(var_location, var, value, **kwargs):
            if saved:
                self.Save(**kwargs)


    # Change the applicable value cell.  Return True if changes were made.
    # Throw exceptions for readonly.
    @default_kwargs(write_to_callables=True, readonly_check=True, fix_range=False)
    def _set_var_value(self, var_location, var, value, **kwargs):
        updated = False

        # print("_set_var_value var_location %s var %s value %s kwargs %s" % (var_location, var, value, kwargs))

        readonly_check = kwargs['readonly_check'] if 'readonly_check' in kwargs else False

        if 'type' in var_location:
            value = eval("%s(%s)" % (var_location['type'], value))

        # Prohibit changing read-only vars
        if readonly_check and 'readonly' in var_location and var_location['readonly']:
            # print("var %s readonly at %s" % (var, var_location))
            raise VarstoreExceptionAccessError(var, extra='is read-only')

        elif 'options' in var_location and value not in var_location['options']:
            raise VarstoreExceptionOption(var, value)

        elif 'range' in var_location and (value < var_location['range'][0] or value > var_location['range'][1]):
            if fix_range:
                # Don't throw a range error - just clamp the value within range
                if value < var_location['range'][0]:
                    value = var_location['range'][0]
                elif value > var_location['range'][1]:
                    value = var_location['range'][1]
            else:
                raise VarstoreExceptionRange(var, value, var_location['range'])

        # If callable, just do the function call if we are allowed ('merge' bypasses this)
        if callable(var_location["value"]):
            if 'write_to_callables' in kwargs and kwargs['write_to_callables']:
                var_location["value"]("set", var, value)

        # If value has changed, set var and indicate save needed
        elif var_location["value"] != value:
            var_location["value"] = value

            # If there is a need to do something after setting.
            if 'publish' in var_location and callable(var_location['publish']):
                var_location['publish'](value, var)
                
            updated = True

        return updated

    @default_kwargs(protecton=DEFAULT_PROTECTION)
    def GetAttributes(self, var, **kwargs):
        if var != None:
            (saved, var_location) = self._findVar(var, self._store, **kwargs)
            attributes = self._get_attributes(var_location)

        else:
            attributes = self._get_attributes({'value': self._store})

        return attributes

    # location contains a list of attributes
    def _get_attributes(self, location):
        attributes = {}

        for attribute in location:
            if attribute == 'value':
                if isinstance(location['value'], dict):
                    fields = {}

                    for var in location['value']:
                        fields[var] = self._get_attributes(location['value'][var])

                    attributes['fields'] = fields

            # Omit callables
            elif not callable(location[attribute]):
                attributes[attribute] = location[attribute]

        return attributes

    @default_kwargs(protectioin=DEFAULT_PROTECTION)
    def Delete(self, var, **kwargs):
        (saved, var_location) = self._findVar(var, self._store, **kwargs)
        if var_location != None:
            del var_location
            if saved:
                self.Save()

    # Merge the src store tree with the dest tree.
    @default_kwargs(protection=DEFAULT_PROTECTION, readonly_check=False)
    def _mergeVarstore(self, dest, src, **kwargs):
        # print("_mergeVarstore %s\n----- into %s\n" % (src, dest))
        for var in src:
            # print("Merging var '%s'" % var)
            if var in dest:
                src_value = src[var]
                if isinstance(src_value, dict):
                    self._mergeVarstore(dest[var]['value'], src_value, **kwargs)

                else:
                    # set var value - ignore changed at this point
                    self._set_var_value(dest[var], var, src_value, write_to_callables=False, fix_range=True, **kwargs)

            else:
                # Unused var - ignore
                pass

    # Apply a set of changes to the store
    @default_kwargs(protection=DEFAULT_PROTECTION)
    def Apply(self, changes, **kwargs):

        if 'var' in kwargs:
            # A var specification allows starting at a particular root of varstore structure
            var = kwargs['var']
            del(kwargs['var'])
            (saved, var_location) = self._findVar(var, self._store, **kwargs)

            var_location = var_location['value']
            # print("Apply var '%s'\n------- with %s\n------ at var_location %s" % (var, changes, var_location))

        else:
            var_location = self._store
            saved = True

        self._mergeVarstore(var_location, changes, **kwargs)
        if saved:
            self.Save()

    # Add a top-level varstore patch to the varstore space
    def AddVarstore(self, varstore):
        self._store.update(varstore)

    @default_kwargs(callables=True, protection=DEFAULT_PROTECTION, ignore_protected=True, not_saved=True)
    def _valuesOf(self, value, **kwargs):
        if isinstance(value, dict):
            results = {}

            for var in value:
                var_location = value[var]

                if (kwargs['callables'] or not callable(var_location['value'])) and (kwargs['not_saved'] or 'not_saved' not in var_location):
                    try:
                        value_protection = DEFAULT_PROTECTION if 'protection' not in var_location else var_location['protection']
                        if value_protection < kwargs['protection']:
                            raise VarstoreExceptionProtectedVar(var)

                        # Resolve to base value
                        results[var] = self._valuesOf(self._get_var_value(var_location, var, **kwargs), **kwargs)

                    except VarstoreExceptionProtectedVar as e:
                        if not kwargs['ignore_protected']:
                            raise e


        else:
            results = value

        return results

    # _findVar('var[.subvar[.subvar]...', varstore, protection)
    # Drill down and return the var cell containing the requested value
    # Returns (saved, location) where 'saved' is True if the var subtree
    # is written to backing storage.  False otherwise.
    @default_kwargs(protection=DEFAULT_PROTECTION)
    def _findVar(self, var, varstore, **kwargs):
        # print("_findVar: var %s\n----- varstore %s\n----- kwargs %s\n" % (var, varstore, kwargs))

        var_location = varstore
        saved = True
        orig_var = var

        # Split the var into it's path and resolve any callables as we descend
        var_list = splitq(var, delim='.')

        # print("var '%s' split to %s" % (var, var_list))
        for v in var_list[:-1]:
            if isinstance(var_location, dict) and v in var_location:
                if 'not_saved' in var_location[v]:
                    saved = False

                last_var_location = var_location
                var_location = var_location[v]['value']

                if callable(var_location):
                    var_location = var_location('get', v)

            else:
                raise VarstoreExceptionUndefinedVar(orig_var)

        if isinstance(var_location, dict) and var_list[-1] in var_location:
            var_location = var_location[var_list[-1]]

        else:
            raise VarstoreExceptionUndefinedVar(orig_var)

        # print("_findVar returning '%s' as %s" % (var, var_location))

        value_protection = DEFAULT_PROTECTION if 'protection' not in var_location else var_location['protection']
        if value_protection < kwargs['protection']:
            raise VarstoreExceptionProtectedVar(orig_var)

        return (saved, var_location)

    @default_kwargs(protection=DEFAULT_PROTECTION)
    def _get_var_value(self, var_location, var, **kwargs):

        value = var_location['value']

        if callable(value):
            # Call user-supplied function to get the value
            value = value("get", var)

        return value

