"""
Utilities that build on top of the built-in ndb.
"""

from google.appengine.ext import ndb
from google.appengine.datastore.datastore_query import Cursor
import types
from collections import namedtuple


class ModelMeta(ndb.model.MetaModel):
    """
    Ensures behaviors are constructed.
    """
    def __init__(cls, name, bases, dct):
        super(ModelMeta, cls).__init__(name, bases, dct)

        # Make sure the Meta class has a proper chain
        if cls.__name__ != 'Model' and not issubclass(cls.Meta, Model.Meta):
            cls.Meta = type('Meta', (cls.Meta, Model.Meta), {})

        # Behaviors
        setattr(cls, 'behaviors', [x(cls) for x in cls.Meta.behaviors])


class Model(ndb.Model):
    """
    ``ndb.Model`` subclass that supports easier callbacks and behaviors.
    """
    __metaclass__ = ModelMeta

    class Meta(object):
        behaviors = ()

    def before_put(self):
        """
        Called before an item is saved.

        :arg self: refers to the item that is about to be saved
        :note: ``self.key`` is invalid if the current item has never been saved
        """
        pass

    def after_put(self, key):
        """
        Called after an item has been saved.

        :arg self: refers to the item that has been saved
        :arg key: refers to the key that the item was saved as
        """
        pass

    @classmethod
    def before_delete(cls, key):
        """
        Called before an item is deleted.

        :arg key: is the key of the item that is about to be deleted. It is okay to ``get()`` this key to interogate the properties of the item.
        """
        pass

    @classmethod
    def after_delete(cls, key):
        """
        Called after an item is deleted.

        :arg key: is the key of the item that was deleted. It is not possible to call ``get()`` on this key.
        """
        pass

    @classmethod
    def before_get(cls, key):
        """
        Called before an item is retrieved. Note that this does not occur for queries.

        :arg key: Is the key of the item that is to be retrieved.
        """
        pass

    @classmethod
    def after_get(cls, key, item):
        """
        Called after an item has been retrieved. Note that this does not occur for queries.

        :arg key: Is the key of the item that was retrieved.
        :arg item: Is the item itself.
        """
        pass

    # Impl details

    @classmethod
    def _invoke_behaviors(cls, method, *args, **kwargs):
        for b in cls.behaviors:
            getattr(b, method)(*args, **kwargs)

    def _pre_put_hook(self):
        self._invoke_behaviors('before_put', self)
        return self.before_put()

    def _post_put_hook(self, future):
        res = future.get_result()
        self._invoke_behaviors('after_put', self)
        return self.after_put(res)

    @classmethod
    def _pre_delete_hook(cls, key):
        cls._invoke_behaviors('before_delete', key)
        return cls.before_delete(key)

    @classmethod
    def _post_delete_hook(cls, key, future):
        cls._invoke_behaviors('after_delete', key)
        return cls.after_delete(key)

    @classmethod
    def _pre_get_hook(cls, key):
        cls._invoke_behaviors('before_get', key)
        return cls.before_get(key)

    @classmethod
    def _post_get_hook(cls, key, future):
        res = future.get_result()
        cls._invoke_behaviors('after_get', res)
        return cls.after_get(key, res)


class Behavior(object):
    """
    Behaviors allow you to encapsulate callbacks into discrete units that can be combined together.
    """
    def __init__(self, Model):
        self.Model = Model

    def before_put(self, instance):
        pass

    def after_put(self, instance):
        pass

    def before_delete(self, key):
        pass

    def after_delete(self, key):
        pass

    def before_get(self, key):
        pass

    def after_get(self, item):
        pass


def key(s):
    if isinstance(s, ndb.Model):
        return s.key
    if isinstance(s, ndb.Key):
        return s
    if isinstance(s, types.StringTypes):
        return ndb.Key(urlsafe=s)
    raise ValueError("Can no coerce value %s into a key." % s)


def get(item):
    if isinstance(item, ndb.Query):
        return item.get()
    return key(item).get()


def put(item):
    item.put()
    return item


def delete(item):
    key(item).delete()
    return item


def check_kind(kind, item):
    if issubclass(kind, ndb.Model):
        kind = kind._get_kind()

    item_key = key(item)
    if not kind == item_key.kind():
        raise ValueError("Incorrect kind %s, expected %s" % (item_key.kind(), kind))

    return item


PaginationResults = namedtuple('PaginationResults', ['items', 'next_page_token'])


def paginate(query, limit=50, page_token=None):
    if page_token and not isinstance(page_token, Cursor):
        page_token = Cursor(urlsafe=page_token)

    # Force all falsy values into None
    if not page_token:
        page_token = None

    data, next_cursor, more = query.fetch_page(limit, start_cursor=page_token)

    return PaginationResults(items=data, next_page_token=next_cursor.urlsafe() if more else None)
