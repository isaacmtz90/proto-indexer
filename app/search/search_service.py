import traceback
import logging
from protorpc import messages
from google.appengine.api import search
from datetime import datetime
import documents
from ferris3 import auto_service, auto_method, Service


class DirectionType(messages.Enum):
    ASCENDING = 1
    DESCENDING = 2


class RefinementMessage(messages.Message):
    name = messages.StringField(1)
    value = messages.StringField(2)


class SortExpressionMessage(messages.Message):
    expression = messages.StringField(1)
    direction = messages.StringField(2)
    default_value = messages.StringField(3)


class QueryMessage(messages.Message):
    query_term = messages.StringField(1)
    indexes = messages.MessageField(documents.FTIndex, 2, repeated=True)
    facet_refinements = messages.MessageField(RefinementMessage, 3, repeated=True)
    get_facets = messages.BooleanField(4)
    stem_fields = messages.StringField(5, repeated=True)
    snippet_fields = messages.StringField(6, repeated=True)
    limit = messages.IntegerField(7)
    offset = messages.IntegerField(8)
    sort_options = messages.MessageField(SortExpressionMessage, 9, repeated=True)


class StatusMessage(messages.Message):
    status = messages.IntegerField(1)
    content = messages.StringField(2)


@auto_service
class SearchDocuments(Service):

    def parse_sort_options(self, sorting_options):
        sort_options = []
        for sortopt in sorting_options:
            sort_options.append(search.SortExpression(expression=sortopt.expression, direction=sortopt.direction))
        return sort_options

    def parse_facets(self, doc_facets):
        facet_options = []
        for facet in doc_facets:
            facet_options.append(search.FacetRefinement(name=facet.name, value=facet.value))
        return facet_options

    @auto_method(returns=StatusMessage)
    def search_core(self, request=(QueryMessage,)):

        options_object = search.QueryOptions(
            limit=getattr(request, 'limit', 20),
            cursor=search.Cursor(),
            offset=getattr(request, 'offset', 0),
            sort_options=search.SortOptions(
                expressions=self.parse_sort_options(getattr(request, 'sort_options', [])),
                limit=1000),
            snippeted_fields=getattr(request, 'snippet_fields', [])
        )

        facet_refinements_object = self.parse_facets(getattr(request, 'facet_refinements', []))
        string_query = getattr(request, 'query_string', '')
        if request.use_stemming:
            string_query = '~' + string_query

        query = search.Query(
            query_string=string_query,
            options=options_object,
            facet_refinements=facet_refinements_object
        )

        try:
            indexes.append(request.indexes)
            my_document = search.Document(
                doc_id=request.id,
                fields=self.parsefields(doc_fields=request.search_fields),
                facets=self.parsefacets(doc_facets=request.search_facets))
            logging.info(len(indexes))
            for index in request.indexes:
                namespace = "default"
                if hasattr(index, 'namespace'):
                    namespace = index.namespace
                index = search.Index(name=index.name, namespace=namespace)
                index.put(my_document)
            return StatusMessage(status=200, content="OK")
        except:
            logging.info(str(traceback.format_exc()))
            return StatusMessage(status=500, content="error")
