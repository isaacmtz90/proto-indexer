import traceback
import logging
from protorpc import messages
from google.appengine.api import search
from datetime import datetime
from ferris3 import auto_service, auto_method, Service


class LanguageType(messages.Enum):
    en = 1
    es = 2
    pt = 3


class FTIndex(messages.Message):
    name = messages.StringField(1)
    namespace = messages.StringField(2)


class DocumentField(messages.Message):
    name = messages.StringField(1)
    value = messages.StringField(2)
    type = messages.StringField(3)


class FacetField(messages.Message):
    name = messages.StringField(1)
    value = messages.StringField(2)
    type = messages.StringField(3)


class IndexedDocument(messages.Message):
    id = messages.StringField(1)
    search_fields = messages.MessageField(DocumentField, 2, repeated=True)
    search_facets = messages.MessageField(FacetField, 3, repeated=True)
    language = messages.EnumField(LanguageType, 4)
    rank = messages.IntegerField(5)
    indexes = messages.MessageField(FTIndex, 6, repeated=True)


class BatchIndexedDocument(messages.Message):
    documents = messages.MessageField(IndexedDocument, 1, repeated=True)
    indexes = messages.MessageField(FTIndex, 2, repeated=True)


class StatusMessage(messages.Message):
    status = messages.IntegerField(1)
    content = messages.StringField(2)


class DocumentMessage(messages.Message):
    content = messages.StringField(1)


@auto_service
class IndexDocuments(Service):

    def parsefields(self, doc_fields):
        parsed_fields = []
        for field in doc_fields:
            if field.type == "text":
                parsed_fields.append(search.TextField(name=field.name, value=field.value))
            elif field.type == "html":
                parsed_fields.append(search.HtmlField(name=field.name, value=field.value))
            elif field.type == "number":
                parsed_fields.append(search.NumberField(name=field.name, value=field.value))
            elif field.type == "date":
                date_to_split = field.value
                days = date_to_split.split("/")
                if int(days[0]) < 10:
                    date_to_split = "0" + date_to_split
                dateval = datetime.strptime(date_to_split, "%m/%d/%Y %H:%M:%S %p")
                parsed_fields.append(search.DateField(name=field.name, value=dateval))
            elif field.type == "atom":
                parsed_fields.append(search.AtomField(name=field.name, value=field.value))
        return parsed_fields

    def parsefacets(self, doc_facets):
        parsed_fields = []
        for field in doc_facets:
            if field.type == "number":
                parsed_fields.append(search.NumberFacet(name=field.name, value=int(field.value)))
            elif field.type == "atom":
                parsed_fields.append(search.AtomFacet(name=field.name, value=field.value))
        return parsed_fields

    @auto_method(returns=StatusMessage)
    def index_document(self, request=(IndexedDocument,)):
        indexes = []

        try:
            indexes.append(request.indexes)
            my_document = search.Document(
                doc_id=getattr(request, 'id', None),
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

    @auto_method(returns=StatusMessage)
    def batch_index(self, request=(BatchIndexedDocument,)):
        indexes = []
        documents = []
        try:
            indexes.append(request.indexes)

            for document in request.documents:
                my_document = search.Document(
                    doc_id=document.id,
                    fields=self.parsefields(doc_fields=document.search_fields),
                    facets=self.parsefacets(doc_facets=document.search_facets))
                documents.append(my_document)

            logging.info("Indexes:" + str(len(indexes)))
            logging.info("Documents:" + str(len(documents)))
            for index in request.indexes:
                namespace = "default"
                if hasattr(index, 'namespace'):
                    namespace = index.namespace
                index = search.Index(name=index.name, namespace=namespace)
                index.put(documents)
            return StatusMessage(status=200, content="OK")
        except:
            logging.info(str(traceback.format_exc()))
            return StatusMessage(status=500, content="error")
