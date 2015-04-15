# -*- coding: utf-8 -*-
from __future__ import absolute_import
from google.appengine.api import memcache
from google.appengine.ext import ndb
from functools import wraps
import datetime
import threading
import inspect


none_sentinel_string = u'☃☸☃ - caching sentinel'


def cache(key, ttl=0, backend=None):
    """
    General-purpose caching decorator. This decorator causes the result of a function
    to be cached so that subsequent calls will return the cached result instead of
    calling the function again. The ttl argument determines how long the cache is valid,
    once the cache is invalid the function will be called to generate a new value and the
    cache will be refreshed. The backend argument can be used to determine how the value
    is cached- by default, the value is stored in memcache but there are built-in backends
    for thread-local caching and caching via the datastore.

    Example::

        @cache('something_expensive', ttl=3600)
        def expensive_function():
            ...

    """
    if backend is None or backend == 'memcache':
        backend = MemcacheBackend
    elif backend == 'local':
        backend = LocalBackend
    elif backend == 'datastore':
        backend = DatastoreBackend

    def wrapper(f):
        @wraps(f)
        def dispatcher(*args, **kwargs):
            data = backend.get(key)

            if data == none_sentinel_string:
                return None

            if data is None:
                data = f(*args, **kwargs)
                backend.set(key, none_sentinel_string if data is None else data, ttl)

            return data

        def cache_getter():
            data = backend.get(key)
            if data == none_sentinel_string:
                return None
            return data

        setattr(dispatcher, 'clear_cache', lambda: backend.delete(key))
        setattr(dispatcher, 'cached', cache_getter)
        setattr(dispatcher, 'uncached', f)
        return dispatcher
    return wrapper


def cache_by_args(key, ttl=0, backend=None):
    """
    Like :func:`cache`, but will use any arguments to the function as part of the key to
    ensure that variadic functions are cached separately. Argument must be able to be
    printed as a string- it's recommended to use plain data types as arguments.
    """
    def wrapper(f):
        argspec = inspect.getargspec(f)[0]

        if len(argspec) and argspec[0] in ('self', 'cls'):
            is_method = True
        else:
            is_method = False

        @wraps(f)
        def dispatcher(*args, **kwargs):
            targs = args if not is_method else args[1:]
            arg_key = "%s:%s:%s" % (key, targs, kwargs)

            @cache(arg_key, ttl, backend=backend)
            def inner_dispatcher():
                return f(*args, **kwargs)

            return inner_dispatcher()
        return dispatcher
    return wrapper


def cache_using_local(key, ttl=0):
    """
    Shortcut decorator for caching using the thread-local cache.
    """
    return cache(key, ttl, backend=LocalBackend)


def cache_using_memcache(key, ttl=0):
    """
    Shortcut decorator for caching using the memcache.
    """
    return cache(key, ttl, backend=MemcacheBackend)


def cache_using_datastore(key, ttl=0):
    """
    Shortcut decorator for caching using the datastore
    """
    return cache(key, ttl, backend=DatastoreBackend)


def cache_by_args_using_local(key, ttl=0):
    """
    Shortcut decorator for caching by arguments using the thread-local cache.
    """
    return cache_by_args(key, ttl, backend=LocalBackend)


def cache_by_args_using_memcache(key, ttl=0):
    """
    Shortcut decorator for caching by arguments using the memcache.
    """
    return cache_by_args(key, ttl, backend=MemcacheBackend)


def cache_by_args_using_datastore(key, ttl=0):
    """
    Shortcut decorator for caching by arguments using the datastore
    """
    return cache_by_args(key, ttl, backend=DatastoreBackend)


class LocalBackend(object):
    """
    The local backend stores caches in a thread-local variable. The caches are available
    for this thread and likely just for the duration of one request.
    """
    cache_obj = threading.local()

    @classmethod
    def set(cls, key, data, ttl):
        if ttl:
            expires = datetime.datetime.now() + datetime.timedelta(seconds=ttl)
        else:
            expires = None
        setattr(cls.cache_obj, key, (data, expires))

    @classmethod
    def get(cls, key):
        if not hasattr(cls.cache_obj, key):
            return None

        data, expires = getattr(cls.cache_obj, key)

        if expires and expires < datetime.datetime.now():
            delattr(cls.cache_obj, key)
            return None

        return data

    @classmethod
    def delete(cls, key):
        try:
            delattr(cls.cache_obj, key)
        except AttributeError:
            pass

    @classmethod
    def reset(cls):
        for a in cls.cache_obj.__dict__.keys():
            delattr(cls.cache_obj, a)


class MemcacheBackend(object):
    """
    Stores caches in memcache. Memcache is available across instances but is subject to
    being dumped from the cache before the expiration time.
    """
    @classmethod
    def set(cls, key, data, ttl):
        memcache.set(key, data, ttl)

    @classmethod
    def get(cls, key):
        return memcache.get(key)

    @classmethod
    def delete(cls, key):
        memcache.delete(key)


class MemcacheCompareAndSetBackend(MemcacheBackend):
    """
    Same as the regular memcache backend but uses compare-and-set logic to ensure
    that memcache updates are atomic.
    """
    @classmethod
    def set(cls, key, data, ttl):
        client = memcache.Client()
        if not client.gets(key):
            memcache.set(key, data, ttl)
            return

        for _ in range(10):
            if client.cas(key, data, ttl):
                break


class DatastoreBackend(object):
    """
    Stores caches in the datastore which has the effect of them being durable and persistent,
    unlike the memcache and local backends. Items stored in the datastore are certain to remain
    until the expiration time passes.
    """
    @classmethod
    def set(cls, key, data, ttl):
        if ttl:
            expires = datetime.datetime.now() + datetime.timedelta(seconds=ttl)
        else:
            expires = None

        DatastoreCacheModel(id=key, data=data, expires=expires).put()

    @classmethod
    def get(cls, key):
        item = ndb.Key(DatastoreCacheModel, key).get()

        if not item:
            return None

        if item.expires and item.expires < datetime.datetime.now():
            item.key.delete()
            return None

        return item.data

    @classmethod
    def delete(cls, key):
        ndb.Key(DatastoreCacheModel, key).delete()


class DatastoreCacheModel(ndb.Model):
    data = ndb.PickleProperty(indexed=False, compressed=True)
    expires = ndb.DateTimeProperty(indexed=False)


class LayeredBackend(object):
    """
    Allows you to use multiple backends at once. When an item is cached it is put
    in to each backend. Retrieval checks each backend in order for the item. This is
    very useful when combining fast but volatile backends (like local) with slow
    but durable backends (like datastore).

    Example::

        @cache('something_expensive', ttl=3600, backend=LayeredBackend(LocalBackend, DatastoreBackend))
        def expensive_function():
            ...

    """
    def __init__(self, *args):
        self.backends = args

    def set(self, key, data, ttl):
        for b in self.backends:
            b.set(key, data, ttl)

    def get(self, key):
        for b in self.backends:
            data = b.get(key)
            if data is not None:
                return data

    def delete(self, key):
        for b in self.backends:
            b.delete(key)
