import webapp2


class BasicHandler(webapp2.RequestHandler):
    def get(self):
        self.response.write("Hello!")


# Ferris will automatically discover these routes
# and add them to the WSGI application.
webapp2_routes = [
    webapp2.Route('/', BasicHandler)
]
