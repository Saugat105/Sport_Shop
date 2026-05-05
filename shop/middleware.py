class NoCacheLoggedInMiddleware:
    """
    Prevents browsers from caching pages while user is logged in.
    This stops the "back button after logout still shows dashboard" issue.

    Sets headers that tell the browser:
      - Don't store this page in cache
      - Always re-fetch from server
      - Treat cached version as expired immediately
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)

        # Apply no-cache headers if user is authenticated
        if hasattr(request, 'user') and request.user.is_authenticated:
            response['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0, private'
            response['Pragma']        = 'no-cache'
            response['Expires']       = '0'

        return response