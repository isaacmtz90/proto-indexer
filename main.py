import endpoints as google_cloud_endpoints
import webapp2
from ferris3.discovery import discover_api_services, discover_webapp2_routes


# APIs
API_CLASSES = discover_api_services()
API_APPLICATION = google_cloud_endpoints.api_server(API_CLASSES)


# WSGI handlers
WSGI_ROUTES = discover_webapp2_routes()
WSGI_APPLICATION = webapp2.WSGIApplication(WSGI_ROUTES)
