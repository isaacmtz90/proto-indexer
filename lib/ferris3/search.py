import logging
import inspect
from collections import namedtuple
from google.appengine.api import search as search_api
from google.appengine.ext import ndb
from .ndb import Behavior


def _datetime_coverter(n, v):
    date = search_api.DateField(name=n, value=v)
    iso = search_api.TextField(name=n + '_iso', value=v.isoformat())
    return date, iso


property_to_field_map = {
    ndb.IntegerProperty: lambda n, v: search_api.NumberField(name=n, value=v),
    ndb.FloatProperty: lambda n, v: search_api.NumberField(name=n, value=v),
    ndb.BooleanProperty: lambda n, v: search_api.AtomField(name=n, value='true' if v else 'false'),
    ndb.StringProperty: lambda n, v: search_api.TextField(name=n, value=v),
    ndb.TextProperty: lambda n, v: search_api.TextField(name=n, value=v),
    # BlobProperty explicitly unindexable
    ndb.DateTimeProperty: _datetime_coverter,
    ndb.DateProperty: lambda n, v: search_api.DateField(name=n, value=v),
    ndb.TimeProperty: lambda n, v: search_api.TextField(name=n, value=v.isoformat()),
    ndb.GeoPtProperty: lambda n, v: search_api.GeoField(name=n, value=search_api.GeoPoint(v.lat, v.lon)),
    # KeyProperty explicity unindexable
    # BlobKeyProperty explicitly unindexable
    ndb.UserProperty: lambda n, v: search_api.TextField(name=n, value=unicode(v)),
    # StructuredProperty explicitly unindexable
    # LocalStructuredProperty explicitly unindexable
    # JsonProperty explicitly unindexable
    # PickleProperty explicity unindexable
    # GenericProperty explicitly unindexable
    # ComputedProperty explicitly unindexable
}

non_repeatable_properties = (
    ndb.DateTimeProperty,
    ndb.DateProperty,
    ndb.TimeProperty,
    ndb.IntegerProperty,
    ndb.FloatProperty
)


class Searchable(Behavior):
    """
    Automatically indexes models during after_put into the App Engine Text Search API.
    """
    def after_put(self, instance):
        only = self.Model.Meta.search_fields if hasattr(self.Model.Meta, 'search_fields') else None
        exclude = self.Model.Meta.search_exclude if hasattr(self.Model.Meta, 'search_exclude') else None
        indexer = self.Model.Meta.search_indexer if hasattr(self.Model.Meta, 'search_indexer') else None
        converters = self.Model.Meta.search_converters if hasattr(self.Model.Meta, 'search_converters') else None
        callback = self.Model.Meta.search_callback if hasattr(self.Model.Meta, 'search_callback') else None
        index_entity(
            instance=instance,
            index=index_for(self.Model),
            only=only,
            exclude=exclude,
            indexer=indexer,
            extra_converters=converters,
            callback=callback)

    def before_delete(self, key):
        unindex_entity(key, index_for(self.Model))


def index_for(Model):
    if hasattr(Model.Meta, 'search_index'):
        return Model.Meta.search_index
    else:
        return 'searchable:%s' % Model._get_kind()


def default_entity_indexer(instance, properties, extra_converters=None):
    results = []

    converters = {}
    converters.update(property_to_field_map)
    if extra_converters:
        converters.update(extra_converters)

    for property in properties:
        value = getattr(instance, property)
        converted = None
        property_instance = instance._properties[property]
        property_class = property_instance.__class__
        converter = converters.get(property_class, converters.get(property, None))

        if not value or not converter:
            if property_class in (ndb.KeyProperty, ndb.BlobKeyProperty):
                logging.debug("Search utilities will not automatically index Key or BlobKey property %s" % property)
            continue

        if not property_instance._repeated:
            converted = converter(property, value)
        else:
            if property_class not in non_repeatable_properties:
                converted = [converter(property, x) for n, x in enumerate(value)]
            else:
                logging.debug("Could not automatically add field %s to the index because date and number fields can not be repeated." % property)

        if not converted:
            continue

        if isinstance(converted, (list, tuple)):
            results.extend(converted)
        else:
            results.append(converted)

    return results


def index_entity(instance, index, only=None, exclude=None, extra_converters=None, indexer=None, callback=None):
    """
    Adds an Model instance into full-text search indexes.

    :param instance: an instance of ndb.Model
    :param list(string) only: If provided, will only index these fields
    :param list(string) exclude: If provided, will not index any of these fields
    :param dict extra_converters: Extra map of property names or types to converter functions.
    :param indexer: A function that transforms properties into search index fields.
    :param callback: A function that will recieve (instance, fields).
        Fields is a map of property names to search. Field instances generated by the indexer
        the callback can modify this dictionary to change how the item is indexed.

    This is usually done in :meth:`Model.after_put <ferris3.ndb.Model.after_put>`, for example::

        def after_put(self):
            index(self)

    """

    indexer = indexer if indexer else default_entity_indexer
    indexes = index if isinstance(index, (list, tuple)) else [index]
    only = only if only else [k for k in instance._properties.keys() if hasattr(instance, k)]
    exclude = exclude if exclude else []
    properties = [x for x in only if x not in exclude]

    fields = indexer(instance, properties, extra_converters=extra_converters)

    if callback:
        callback(instance=instance, fields=fields)

    try:
        doc = search_api.Document(doc_id=str(instance.key.urlsafe()), fields=fields)

        for index_name in indexes:
            index = search_api.Index(name=index_name)
            index.put(doc)

    except Exception as e:
        logging.error("Adding model %s instance %s to the full-text index failed" % (instance.key.kind(), instance.key.id()))
        logging.error("Search API error: %s" % e)
        raise


def unindex_entity(instance_or_key, index=None):
    """
    Removes a document from the full-text search.

    This is usually done in :meth:`Model.after_delete <ferris3.ndb.Model.after_delete>`, for example::

        @classmethod
        def after_delete(cls, key):
            unindex(key)

    """
    if isinstance(instance_or_key, ndb.Model):
        instance_or_key = instance_or_key.key

    indexes = index if isinstance(index, (list, tuple)) else [index]

    for index_name in indexes:
        index = search_api.Index(name=index_name)
        index.delete(str(instance_or_key.urlsafe()))


def to_entities(results):
    """
    Transform a list of search results into ndb.Model entities by using the document id
    as the urlsafe form of the key.
    """
    if isinstance(results, SearchResults):
        items = [x for x in ndb.get_multi([ndb.Key(urlsafe=y.doc_id) for y in results.items]) if x]
        return SearchResults(items=items, error=results.error, next_page_token=results.next_page_token)
    else:
        return[x for x in ndb.get_multi([ndb.Key(urlsafe=y.doc_id) for y in results]) if x]


SearchResults = namedtuple('SearchResults', ['items', 'error', 'next_page_token'])


def search(index, query, sort=None, sort_default_values=None, limit=None, page_token=None, ids_only=True, options=None, per_document_cursor=False):
    """
    Searches an index with the given query and returns a list of document ids or search documents.

     To get the full search document pass ``ids_only = False``.

    :param index: The name of the index to search.
    :param query: Query string as described in `the App Engine documentation <https://developers.google.com/appengine/docs/python/search/query_strings>`__.
    :param sort: A sort string, can be ``"field_name"`` for ascending or ``"-field_name"`` for descending. Can also be a list of sorts, such as ``["price", "-rating"]``.
    :param sort_default_values: The default value to use for sorting if there is no value in the document.
    :param limit: Maximum number of results to return.
    :param page_token: Cursor used to get a particular page of results.
    :param ids_only: By default, this only returns document ids as the most common use case is to get the entity or
        database entries associated with the document. Pass ``False`` here to get the complete document.
    :param options: Advanced options that are passed directly to ``index.search``. See `query options <https://developers.google.com/appengine/docs/python/search/options>`__.
    :param per_document_cursor: Whether to include a cursor for every document or not.
    :returns: a tuple of ``(items, error, next_page_token)``

    Examples::

        # Search all pages for "policies"
        results, error, next_page_token = search('searchable:Page', 'policies', limit=20)

        # Search all products for "rake" sorted by price descending
        results, error, next_page_token = search('searchable:Page', 'rake', sort='-price', limit=20)
    """

    options = options if options else {}
    error = None
    results = []
    current_cursor = None
    next_cursor = None

    try:
        index = search_api.Index(name=index)
        current_cursor = search_api.Cursor(web_safe_string=page_token) if page_token else search_api.Cursor(per_result=per_document_cursor)

        options_params = dict(
            limit=limit,
            ids_only=ids_only,
            cursor=current_cursor)

        if sort:
            options_params['sort_options'] = create_sort_options(sort, sort_default_values)

        options_params.update(options)

        # if limit is none, remove it, as it'll cause issues.
        if options_params.get('limit') is None:
            del options_params['limit']

        query = search_api.Query(query_string=query, options=search_api.QueryOptions(**options_params))
        index_results = index.search(query)

        results = list(index_results)

        current_cursor = current_cursor.web_safe_string if current_cursor else None
        next_cursor = index_results.cursor.web_safe_string if index_results.cursor and results else None

    except (search_api.Error, search_api.query_parser.QueryException) as e:
        error = str(e)

    return SearchResults(items=results, error=error, next_page_token=next_cursor)


def create_sort_options(fields, default_values=None):
    default_values = default_values or {}
    expressions = []

    fields = fields if isinstance(fields, (list, tuple)) else [fields]

    for field in fields:
        if isinstance(field, search_api.SortExpression):
            expressions.append(field)
            continue

        if field.startswith('-'):
            field = field[1:]
            direction_exp = search_api.SortExpression.DESCENDING
        else:
            direction_exp = search_api.SortExpression.ASCENDING

        default_value = default_values.get(field, '')

        if inspect.isfunction(default_value):
            default_value = default_value(field, direction_exp)

        expressions.append(
            search_api.SortExpression(
                expression=field,
                direction=direction_exp,
                default_value=default_value
            ))

    return search_api.SortOptions(expressions=expressions)


def join_query(filters, operator='AND', parenthesis=False):
    """
    Utility function for joining muliple queries together
    """
    operator = ' %s ' % operator
    filters = [x for x in filters if x]
    if parenthesis:
        filters = ["(%s)" % x for x in filters]
    return operator.join(filters)
