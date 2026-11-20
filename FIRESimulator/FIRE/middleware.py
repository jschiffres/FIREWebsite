PRIVATE_PREFIXES = (
    '/plan/', '/myplans/', '/account/', '/new/', '/compare/', '/downloadplan/', '/downloadpdf/',
    '/copyplan/', '/renameplan/', '/deleteplan/', '/billing/', '/admin/',     '/password-change/', '/lab/',
)


class NoIndexPrivatePagesMiddleware:
    """Mark signed-in pages noindex. They must stay crawlable (not Disallowed in robots.txt) or Google
    can't see the header and reports them as 'Indexed, though blocked by robots.txt'."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        if request.path.startswith(PRIVATE_PREFIXES):
            response['X-Robots-Tag'] = 'noindex, nofollow'
        return response
