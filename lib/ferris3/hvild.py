import ferris3

#
# Method implementations.
# Bare-bones, can be re-used in other methods and such.
#


def list_impl(ListMessage, query):
    return ferris3.ToolChain(query) \
        .messages.serialize_list(ListMessage) \
        .value()


def paginated_list_impl(ListMessage, query, limit, pageToken):
    return ferris3.ToolChain(query) \
        .ndb.paginate(limit=limit, page_token=pageToken) \
        .messages.serialize_list(ListMessage) \
        .value()


def searchable_list_impl(ListMessage, index, query, limit, sort, pageToken):
    def check_for_search_errors(data):
        if data.error:
            raise ferris3.BadRequestException("Search error: %s" % data.error)

    return ferris3.ToolChain(query) \
        .search.search(index, sort=sort, limit=limit, page_token=pageToken) \
        .tap(check_for_search_errors) \
        .search.to_entities() \
        .messages.serialize_list(ListMessage) \
        .value()


def get_impl(Model, Message, itemId):
    return ferris3.ToolChain(itemId) \
        .ndb.get() \
        .raise_if(None, ferris3.NotFoundException()) \
        .ndb.check_kind(Model) \
        .messages.serialize(Message) \
        .value()


def delete_impl(Model, itemId):
    return ferris3.ToolChain(itemId) \
        .ndb.key() \
        .ndb.check_kind(Model) \
        .ndb.delete() \
        .value()


def update_impl(Model, Message, itemId, request):
    item = ferris3.ToolChain(itemId) \
        .ndb.get() \
        .raise_if(None, ferris3.NotFoundException()) \
        .ndb.check_kind(Model) \
        .value()

    return ferris3.ToolChain(request) \
        .messages.deserialize(item) \
        .ndb.put() \
        .messages.serialize(Message) \
        .value()


def insert_impl(Model, Message, request):
    return ferris3.ToolChain(request) \
        .messages.deserialize(Model) \
        .ndb.put() \
        .messages.serialize(Message) \
        .value()

#
# Full method wrappers.
# Can be used as endpoint methods directly.
#


def list(Model, Message=None, ListMessage=None, query=None, name='list'):
    """
    Implements a very simple list method for the given model.

    .. warning:: No limiting logic is applied to the query so this will attempt to get all results.
        It is almost always preferable to use :func:`paginated_list`.

    """
    if not Message:
        Message = ferris3.model_message(Model)

    if not ListMessage:
        ListMessage = ferris3.list_message(Message)

    if not query:
        query = Model.query()

    if callable(query):
        query = query()

    @ferris3.auto_method(returns=ListMessage, name=name)
    def inner(self, request):
        return list_impl(ListMessage, query)

    return inner


def paginated_list(Model, Message=None, ListMessage=None, query=None, limit=50, name='paginated_list'):
    """
    Similar to :func:`list` but returns results in pages of ``limit`` size.
    """
    if not Message:
        Message = ferris3.model_message(Model)

    if not ListMessage:
        ListMessage = ferris3.list_message(Message)

    if not query:
        query = Model.query()

    if callable(query):
        query = query()

    @ferris3.auto_method(returns=ListMessage, name=name)
    def inner(self, request, pageToken=(str, '')):
        return paginated_list_impl(ListMessage, query, limit, pageToken)

    return inner


def searchable_list(Model=None, Message=None, ListMessage=None, limit=50, index=None, name='search'):
    """
    Implements a search method by using the :mod:`~ferris3.search` module. This method assumes you are
    using the common use case of indexing datastore entities and does not work for generic searches.
    """
    if not Message:
        Message = ferris3.model_message(Model)

    if not ListMessage:
        ListMessage = ferris3.list_message(Message)

    if not index:
        index = ferris3.search.index_for(Model)

    @ferris3.auto_method(returns=ListMessage, name=name)
    def inner(self, request, query=(str, ''), sort=(str, None), pageToken=(str, '')):
        return searchable_list_impl(ListMessage, index, query, limit, sort, pageToken)

    return inner


def get(Model, Message=None, name='get'):
    """
    Implements a straightfoward get method by using the urlsafe version of the entity's key.
    """
    if not Message:
        Message = ferris3.model_message(Model)

    @ferris3.auto_method(returns=Message, name=name)
    def inner(self, request, itemId=(str,)):
        return get_impl(Model, Message, itemId)

    return inner


def delete(Model, name='delete'):
    """
    Implements a straightfoward delete method by using the urlsafe version of the entity's key.
    """

    @ferris3.auto_method(name=name, http_method='DELETE')
    def inner(self, request, itemId=(str,)):
        delete_impl(Model, itemId)
        return None

    return inner


def insert(Model, Message=None, name='insert'):
    """
    Implements the insert method. The request fields are determined by the ``Message`` parameter.
    """
    if not Message:
        Message = ferris3.model_message(Model)

    @ferris3.auto_method(returns=Message, name=name, http_method='POST')
    def inner(self, request=(Message,)):
        return insert_impl(Model, Message, request)

    return inner


def update(Model, Message=None, name='update'):
    """
    Implements the update method. The item updated is determined by the urlsafe key of that item.
    The request fields are determined by the ``Message`` parameter.
    """
    if not Message:
        Message = ferris3.model_message(Model)

    @ferris3.auto_method(returns=Message, name=name, http_method='POST')
    def inner(self, request=(Message,), itemId=(str,)):
        return update_impl(Model, Message, itemId, request)

    return inner
