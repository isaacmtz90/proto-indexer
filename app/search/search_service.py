import traceback
import logging
from protorpc import messages
from google.appengine.api import search
from ferris3 import auto_service, auto_method, Service


class FTIndex(messages.Message):
    name = messages.StringField(1)
    namespace = messages.StringField(2)


class RefinementMessage(messages.Message):
    name = messages.StringField(1)
    value = messages.StringField(2)


class SortExpressionMessage(messages.Message):
    expression = messages.StringField(1)
    direction = messages.StringField(2)


class FieldMessage(messages.Message):
    name = messages.StringField(1)
    value = messages.StringField(2)


class QueryMessage(messages.Message):
    query_string = messages.StringField(1, required=True)
    index = messages.MessageField(FTIndex, 2, required=True)
    facet_refinements = messages.MessageField(RefinementMessage, 3, repeated=True)
    get_facets = messages.BooleanField(4)
    use_stemming = messages.BooleanField(5)
    snippet_fields = messages.StringField(6, repeated=True)
    limit = messages.IntegerField(7)
    offset = messages.IntegerField(8)
    sort_options = messages.MessageField(SortExpressionMessage, 9, repeated=True)


class StatusMessage(messages.Message):
    status = messages.IntegerField(1)
    content = messages.StringField(2)


class FacetValueMessage(messages.Message):
    count = messages.IntegerField(1)
    label = messages.StringField(2)


class FacetDetailsMessage(messages.Message):
    name = messages.StringField(1)
    values = messages.MessageField(FacetValueMessage, 2, repeated=True)


class ScoredDocumentMessage(messages.Message):
    doc_id = messages.StringField(1)
    fields = messages.MessageField(FieldMessage, 2, repeated=True)
    language = messages.StringField(3)
    rank = messages.StringField(4)
    expressions = messages.MessageField(FieldMessage, 5, repeated=True)


class SearchResultsMessage(messages.Message):
    found = messages.IntegerField(1)
    results = messages.MessageField(ScoredDocumentMessage, 2, repeated=True)
    facets = messages.MessageField(FacetDetailsMessage, 3, repeated=True)
    error_message = messages.StringField(4)
    status = messages.IntegerField(5)


@auto_service
class SearchDocuments(Service):

    def parse_sort_options(self, sorting_options):
        sort_options = []
        for sortopt in sorting_options:
            if getattr(sortopt, 'direction') in ["ASCENDING", "DESCENDING"]:
                direction = search.SortExpression.DESCENDING
                if sortopt.direction == "ASCENDING":
                    direction = search.SortExpression.ASCENDING
                sort_options.append(search.SortExpression(expression=sortopt.expression, direction=direction))
            else:
                raise Exception("Sort option not valid: %s" % sortopt.direction)

        return sort_options

    def parse_facets(self, doc_facets):
        facet_options = []
        for facet in doc_facets:
            facet_options.append(search.FacetRefinement(name=facet.name, value=facet.value))
        return facet_options

    def parse_fields(self, doc_fields):
        fields_found = []
        for field in doc_fields:
            fields_found.append(FieldMessage(name=field.name, value=field.value))
        return fields_found

    def parse_expressions(self, doc_expressions):
        found_expressions = []
        for expression in doc_expressions:
            found_expressions.append(FieldMessage(name=expression.name, value=expression.value))
        return found_expressions

    def parse_found_facets(self, doc_facets):
        facets_found = []
        for facet in doc_facets:
            facets_found.append(FacetValueMessage(label=facet.label, count=facet.count))
        return facets_found

    @auto_method(returns=SearchResultsMessage)
    def search_core(self, request=(QueryMessage,)):
        limitval = 20
        if request.limit is not None:
            limitval = request.limit
        options_object = search.QueryOptions(
            limit=limitval,
            offset=getattr(request, 'offset', None),
            sort_options=search.SortOptions(
                expressions=self.parse_sort_options(getattr(request, 'sort_options', [])),
                limit=1000),
            snippeted_fields=getattr(request, 'snippet_fields', []),
            ids_only=getattr(request, 'ids_only', False)
        )

        facet_refinements_object = self.parse_facets(getattr(request, 'facet_refinements', []))
        string_query = getattr(request, 'query_string', '')
        if getattr(request, 'use_stemming', False):
            string_query = '~%s' % string_query.strip()

        query = search.Query(
            query_string=string_query,
            options=options_object,
            facet_refinements=facet_refinements_object,
            enable_facet_discovery=getattr(request, "get_facets", False)
        )

        try:

            requested_index = request.index
            namespace = "default"
            if hasattr(requested_index, 'namespace'):
                namespace = requested_index.namespace
            index = search.Index(name=requested_index.name, namespace=namespace)
            result = []
            if index:
                documents_found = []
                facets_found = []
                result_count = 0
                result = index.search(query)
                for document in result.results:
                    documents_found.append(ScoredDocumentMessage(
                        doc_id=document.doc_id,
                        fields=self.parse_fields(document.fields),
                        language=getattr(document, 'language', 'en'),
                        rank=str(getattr(document, 'rank', 0)),
                        expressions=self.parse_expressions(getattr(document, 'expressions', []))))
                for facet in result.facets:
                    facets_found.append(FacetDetailsMessage(
                        name=facet.name,
                        values=self.parse_found_facets(getattr(facet, 'values', []))))

                result_count = result.number_found

            return SearchResultsMessage(found=result_count,
                                        results=documents_found,
                                        facets=facets_found,
                                        status=200,
                                        error_message="")
        except:
            logging.info(str(traceback.format_exc()))
            return SearchResultsMessage(status=500, content=str(traceback.format_exc()))
