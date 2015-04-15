import functools
import logging
import types
import inspect


def partial(func):
    @functools.wraps(func)
    def inner(*args, **kwargs):
        return functools.partial(func, *args, **kwargs)
    setattr(inner, '_f3_partial', True)
    return inner


def tap(func, data):
    func(data)
    return data


def pipe(func, data):
    return func(data)


def raise_if(value_or_func, ex, data):
    if callable(value_or_func):
        if value_or_func(data):
            raise ex
    elif value_or_func == data:
        raise ex

    return data


class mixedmethod(object):
    def __init__(self, func):
        self.func = func

    def __get__(self, instance, cls):
        return functools.partial(self.func, instance, cls)


class Chain(object):
    def __init__(self, value=None, use=None):
        self._modules = {}
        self.set_value(value)

        if use:
            for m in use:
                self.add_chain_module(m)

    def _chain_ref(self):
        return self

    def get_value(self):
        return self._value

    def set_value(self, value):
        self._value = value
        return self

    value = get_value

    @mixedmethod
    def add_chain_function(self, cls, func, name=None):
        if not name:
            name = func.__name__

        # Curry if needed
        if not hasattr(func, '_f3_partial'):
            func = partial(func)

        # Wrap with the call adapter
        @functools.wraps(func)
        def call_wrapper(func):
            def inner(self, *args, **kwargs):
                val = self.get_value()
                try:
                    val = func(*args, **kwargs)(val)
                except:
                    logging.error("Problem occurred while executing chain '%s' with data '%s' and args %s, %s" % (func.__name__, val, args, kwargs))
                    raise

                self.set_value(val)
                return self._chain_ref()
            return inner

        func = call_wrapper(func)

        if self:
            setattr(self, name, types.MethodType(func, self))
        else:
            setattr(cls, name, func)

    @classmethod
    def add_chain_functions(cls, *funcs):
        for func in funcs:
            cls.add_chain_function(func)

    @mixedmethod
    def add_chain_module(self, cls, module, module_name=None, only=None, exclude=None):
        if not module_name:
            module_name = module.__name__.split('.').pop()

        def get_mod(self):
            if module_name in self._modules:
                return self._modules[module_name]

            cm = ChainModule(self)
            for fname, func in inspect.getmembers(module, callable):
                if only and fname not in only:
                    continue
                if exclude and fname in exclude:
                    continue
                cm.add_chain_function(func, fname)

            self._modules[module_name] = cm
            return cm

        # If it's a class, add it to all instances and lazy load
        if not self:
            setattr(cls, module_name, property(get_mod))

        # If this is an instance, just go ahead and add it.
        else:
            setattr(self, module_name, get_mod(self))


class ChainModule(Chain):
    def __init__(self, parent):
        self._parent = parent

    def _chain_ref(self):
        return self._parent

    def get_value(self):
        return self._parent.get_value()

    def set_value(self, value):
        self._parent.set_value(value)
        return self._parent

    value = get_value

    add_chain_module = None


# Add built-ins
Chain.add_chain_functions(
    tap,
    pipe,
    raise_if
)
