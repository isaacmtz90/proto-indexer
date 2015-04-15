# LICENSE
# =======

# Copyright (c) 2013, Tripp Lilley <tripplilley@gmail.com>
# All rights reserved.

# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are
# met:

# - Redistributions of source code must retain the above copyright
#   notice, this list of conditions and the following disclaimer.

# - Redistributions in binary form must reproduce the above copyright
#   notice, this list of conditions and the following disclaimer in the
#   documentation and/or other materials provided with the distribution.

# - Neither `Agoraplex`, nor the names of its contributors may be used
#   to endorse or promote products derived from this software without
#   specific prior written permission.

# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
# "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
# LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR
# A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT
# HOLDER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL,
# SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT
# LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE,
# DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY
# THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
# (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
# OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

# anodi
from collections import OrderedDict
import inspect
empty = object()

def returns (annotation):
    """
    Decorator to add ``annotation`` to ``func``'s ``return``
    annotation, as though it were a Python 3 ``-> ...`` annotation.

        >>> from anodi import returns
        >>> @returns(int)
        ... def example ():
        ...    pass
        ...
        >>> example.__annotations__
        {'return': <type 'int'>}
    """
    def annotate (func):
        func.__annotations__ = getattr(func, '__annotations__', {})
        if not annotation is empty:
            func.__annotations__['return'] = annotation
        return func
    return annotate

def annotated (func=None, returns=empty):
    """
    Decorator to treat ``func``'s default args as a combination of
    annotations and default values, migrating the annotations to
    ``func.__annotations__``, leaving only the defaults in
    ``__defaults__``).

    The optional ``returns`` keyword parameter is placed in the
    resulting ``__annotations__`` dict.

    Each default value must be a tuple, ``(annotation, default)``. To
    supply an unannotated parameter with a default value, use the
    ``empty`` marker object. To supply an annotation without a
    default value, use a 1-tuple: ``(annotation,)``.

    Note that the Python 2.x rules prohibiting non-default parameters
    from coming after defaults still apply, but we don't enforce those
    rules. The effect of using the ``(annotation,)`` form *after*
    using the ``(annotation, default)`` form is likely to be
    surprising, at best.

    You may specify an unannotated parameter by using an empty tuple
    as its default value. This is to allow placing unannotated
    parameters after annotated parameters. Ordinarily, this would not
    be allowed, since the annotated parameter would mark the start of
    default values, requiring defaults on all subsequent parameters.

    We do *not* support nested tuple parameters.

    We also don't yet have a way to add annotations to the ``*args``
    or ``**kwargs`` catch-all parameters, since they don't take
    defaults.

    Example:

        >>> from anodi import annotated, empty
        >>> @annotated
        ... def example (a, b, c=(int,), d=(), e=(empty, "hi")):
        ...    pass
        ...
        >>> example.__annotations__
        {'c': <type 'int'>}
        >>> example.__defaults__
        ('hi',)

        >>> @annotated(returns=int)
        ... def example (a, b, c=(int,), d=(), e=(empty, "hi")):
        ...    pass
        ...
        >>> example.__annotations__
        {'c': <type 'int'>, 'return': <type 'int'>}
        >>> example.__defaults__
        ('hi',)

    """

    def annotate (func):
        func.__annotations__ = getattr(func, '__annotations__', OrderedDict())

        if not returns == empty:
            func.__annotations__['return'] = returns

        defaults = func.__defaults__
        if defaults:
            spec = inspect.getargspec(func)
            # ___TODO:___ support *args, **kwargs annotation?

            # extract annotations
            nanno = len(defaults)
            for (i, name) in enumerate(spec.args[-nanno:]):
                if len(defaults[i]) < 1 or defaults[i][0] is empty:
                    continue
                func.__annotations__[name] = defaults[i][0]

            # prune annotations, leaving only defaults
            defaults = tuple((d[1]
                              for d in func.__defaults__
                              if len(d) > 1))
            # use ``None`` if there are no defaults left, since that's
            # how a function without any defaults would come out.
            func.__defaults__ = defaults or None
        return func

    # if we were called without a ``results`` argument, then we're
    # directly decorating ``func``:
    if returns == empty:
        return annotate(func)

    # otherwise, we're indirectly decorating, via ``annotate``:
    return annotate
