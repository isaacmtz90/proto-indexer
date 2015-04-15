import jinja2
import os

_debug = os.environ.get('SERVER_SOFTWARE', '').startswith('Dev')
_environment = None


def environment():
    global _environment
    if _environment:
        return _environment

    jinja2_env_kwargs = {
        'loader': jinja2.FileSystemLoader(os.getcwd()),
        'auto_reload': False,
        'cache_size': 0 if _debug else 50,
    }
    _environment = jinja2.Environment(**jinja2_env_kwargs)
    return _environment


def render(name, context=None):
    env = environment()
    template = env.get_or_select_template(name)
    context = context if context else {}

    result = template.render(context)
    return result
