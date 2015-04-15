from __future__ import absolute_import
from protorpc import message_types
from protorpc import messages
import endpoints
from .anodi import annotated
import inspect
import re
import yaml
import os

_endpoints = {}
_default_endpoint_name = None

base_directory = os.getcwd()


def add(config_or_file, default=False):
    """
    Add an endpoint to the registry.

    ``config_or_file`` can be the path to a yaml definition file or a dictionary of arguments to pass to
    ``endpoints.api``. See also Google's documentation on `endpoints.api <https://developers.google.com/appengine/docs/python/endpoints/create_api#defining_the_api_endpointsapi>`__.

    Tpyically, this is called in an application's ``main.py`` before any services are loaded.

    Examples::

        ferris3.endpoints.add('app/default-endpoint.yaml', default=True)
        ferris3.endpoints.add({
            name: 'test',
            version: 'v1'
        })
    """
    global _endpoints, _default_endpoint_name

    if isinstance(config_or_file, (str, unicode)):
        config = load_config_file(config_or_file)
    else:
        config = config_or_file

    api = endpoints.api(**config)
    _endpoints[config['name']] = api

    if default:
        _default_endpoint_name = config['name']

    return api


def get(name=None):
    """
    Get an endpoint by name from the registry.

    The value returned is a normal `endpoints.api <https://developers.google.com/appengine/docs/python/endpoints/create_api#creating_an_api_implemented_with_multiple_classes>`_ class that can be used exactly as descibed in the Google documentionat.

    ``name`` is the value of the ``name`` configuration field given for the endpoint. If no name is provided, it'll return the default endpoint.

    Examples::

        endpoint = ferris3.endpoints.get('ferris')

        @endpoint.api_class(resource_name='shelves')
        class ShelvesService(remote.Service):
            ...

    """
    if not name:
        if not _default_endpoint_name:
            raise RuntimeError("No default endpoint has been configured")
        name = _default_endpoint_name

    return _endpoints.get(name)


def default():
    """
    Simply calls :func:`get` for the default endpoint.
    """
    return get()


def get_all():
    return _endpoints.values()


def load_config_file(config_file):
    with open(os.path.join(base_directory, config_file)) as f:
        config = yaml.load(f)

    # Replace constants
    recursive_replace(config, 'API_EXPLORER_CLIENT_ID', endpoints.API_EXPLORER_CLIENT_ID)
    recursive_replace(config, 'USERINFO', 'https://www.googleapis.com/auth/userinfo.email')

    auth_level = config.get('auth_level', 'optional')
    config['auth_level'] = {
        'required': endpoints.AUTH_LEVEL.REQUIRED,
        'optional': endpoints.AUTH_LEVEL.OPTIONAL,
        'optional_continue': endpoints.AUTH_LEVEL.OPTIONAL_CONTINUE,
        'none': endpoints.AUTH_LEVEL.NONE
    }.get(auth_level)

    return config


def recursive_replace(container, old, new):
    if isinstance(container, dict):
        for key, value in container.iteritems():
            if value == old:
                container[key] = new
            if isinstance(value, (dict, list)):
                recursive_replace(value, old, new)
    else:
        for ix, value in enumerate(container):
            if value == old:
                container[ix] = new


def underscore(string):
    s1 = re.sub('(.)([A-Z][a-z]+)', r'\1_\2', string)
    return re.sub('([a-z0-9])([A-Z])', r'\1_\2', s1).lower()


def auto_service(cls=None, endpoint=None, **kwargs):
    """
    Automatically configures and adds a ``remote.Service`` class to the endpoint service registry.

    If ``endpoint`` is None then the default endpoint will be used. If it is a string then the endpoint will be looked up in the registry using :func:`get`.

    The ``resource_name`` and ``path`` configuration options are automatically determined from the class name.
    For example, "PostsService" becomes "posts" and "FuzzyBearsService" becomes "fuzzy_bears". These can be overriden by
    passing in the respecitve kwargs.

    All kwargs are passed directly through to `endpoints.api_class <https://developers.google.com/appengine/docs/python/endpoints/create_api#creating_an_api_implemented_with_multiple_classes>`_.

    Examples::

        @ferris3.auto_service
        class PostsService(ferris3.Service):
            ...

        @ferris3.auto_service(endpoint='mobile_only', resource_name='posts', path='posts')
        class MobilePostsService(ferris3.Service):
            ...

    """
    def auto_class_decr(cls):
        if 'resource_name' not in kwargs:
            name = underscore(cls.__name__).replace('_api', '').replace('_service', '')
            kwargs['resource_name'] = name

        if 'path' not in kwargs:
            kwargs['path'] = kwargs['resource_name']

        ep_api = get(endpoint)
        return ep_api.api_class(**kwargs)(cls)

    if cls:
        return auto_class_decr(cls)
    return auto_class_decr


def auto_method(func=None, returns=message_types.VoidMessage, name=None, http_method='POST', **kwargs):
    """
    Uses introspection to automatically configure and expose an API method. This is sugar around `endpoints.method <https://developers.google.com/appengine/docs/python/endpoints/create_api#defining_an_api_method_endpointsmethod>`_.

    The ``returns`` argument is the response message type and is by default ``message_types.VoidMessage`` (an empty response).
    The ``name`` argument is optional and if left out will be set to the name of the function.
    The ``http_method`` argument is ``POST`` by default and can be changed if desired. Note that ``GET`` methods can not accept a request message.
    The remaining ``kwargs`` are passed direction to ``endpoints.method``.

    This decorator uses introspection along with annotation to determine the request message type as well as any query string parameters for the method. This saves you the trouble of having to define a `ResourceContainer <https://developers.google.com/appengine/docs/python/endpoints/create_api#using_resourcecontainer_for_path_or_querystring_arguments>`_.

    Examples::

        # A method that takes nothing and returns nothing.
        @auto_method
        def nothing(self, request):
            pass

        # A method that returns a simple message
        @auto_method(returns=SimpleMessage)
        def simple(self, request):
            return SimpleMessage(content="Hello")

        # A method that takes a simple message as a request
        @auto_method
        def simple_in(self, request=(SimpleMessage,)):
            pass

        # A method that takes 2 required parameters and one optional one.
        @auto_method
        def params(self, request, one=(str,), two=(int,), three=(str, 'I am default')):
            pass

    """
    def auto_api_decr(func):
        func_name = func.__name__ if not name else name
        func = annotated(returns=returns)(func)
        f_annotations = func.__annotations__
        f_args, f_varargs, f_kwargs, f_defaults = inspect.getargspec(func)

        if f_defaults:
            f_args_to_defaults = {f_args[len(f_args) - len(f_defaults) + n]: x for n, x in enumerate(f_defaults)}
        else:
            f_args_to_defaults = {}

        RequestMessage = f_annotations.pop('request', message_types.VoidMessage)
        ResponseMessage = f_annotations.pop('return', message_types.VoidMessage)

        RequestMessageOrContainer, request_args = annotations_to_resource_container(f_annotations, f_args_to_defaults, RequestMessage)

        sanity_check_request_message(func_name, RequestMessageOrContainer)

        ep_dec = endpoints.method(
            RequestMessageOrContainer,
            ResponseMessage,
            http_method=http_method,
            name=func_name,
            path=func_name,  #TODO: include required params,
            **kwargs
        )

        def inner(self, request):
            kwargs = {}
            for arg_name in request_args:
                if hasattr(request, arg_name):
                    kwargs[arg_name] = getattr(request, arg_name)
                if arg_name in f_args_to_defaults and kwargs.get(arg_name) is None:
                    kwargs[arg_name] = f_args_to_defaults[arg_name]

            return_val = func(self, request, **kwargs)

            # return voidmessage if the return val is none
            if ResponseMessage == message_types.VoidMessage and return_val is None:
                return message_types.VoidMessage()

            return return_val

        return ep_dec(inner)

    if func:
        return auto_api_decr(func)

    return auto_api_decr


def annotations_to_resource_container(annotations, defaults, RequestMessage):
    args = {}

    if annotations:
        for n, (name, type) in enumerate(annotations.iteritems(), 1):
            required = True if name not in defaults else False
            default = defaults[name] if not required else None

            if type == str:
                args[name] = messages.StringField(n, required=required, default=default)
            elif type == int:
                args[name] = messages.IntegerField(n, required=required, default=default)
            elif type == bool:
                args[name] = messages.BooleanField(n, required=required, default=default)
            elif type == float:
                args[name] = messages.FloatField(n, required=required, default=default)
            else:
                raise ValueError("Unsupported endpoints argument type: %s" % type)

    if args:
        return endpoints.ResourceContainer(RequestMessage, **args), args.keys()

    return RequestMessage, args.keys()


def sanity_check_request_message(method, message):
    if hasattr(message, 'combined_message_class'):
        message = message.combined_message_class
    field_names = set([x.name for x in message.all_fields()])
    reserved_fields = set(['access_token', 'callback', 'fields', 'key', 'printPrint', 'quotaUser', 'userIp'])
    bad_fields = field_names & reserved_fields

    if bad_fields:
        raise ValueError("Request type %s for method %s contains reserved field names: %s" % (message, method, ', '.join(bad_fields)))
