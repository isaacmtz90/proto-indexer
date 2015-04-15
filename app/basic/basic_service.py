from protorpc import messages
from ferris3 import auto_service, auto_method, Service


class BasicMessage(messages.Message):
    content = messages.StringField(1)


@auto_service
class BasicService(Service):

    @auto_method(returns=BasicMessage)
    def get(self, request):
        return BasicMessage(content="Hello, Ferris!")
