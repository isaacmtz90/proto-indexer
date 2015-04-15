from .chain import Chain
from . import ndb, messages, search


class ToolChain(Chain):
    pass


ToolChain.add_chain_module(ndb)
ToolChain.add_chain_module(messages)
ToolChain.add_chain_module(search, only=("search", "to_entities"))
