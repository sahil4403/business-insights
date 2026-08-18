from django.shortcuts import redirect


class StrictAdminSecurityMiddleware:
    """
    Middleware for Django Administration access.
    Allows authenticated staff/superuser accounts seamless access without double-login,
    while protecting /admin/ from unauthenticated users.
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        path = request.path

        # Target all /management-portal-x99/ routes
        if path.startswith('/management-portal-x99/'):
            # Allow admin login page and static assets
            if path.startswith('/management-portal-x99/login/') or path.startswith('/management-portal-x99/jsi18n/') or path.startswith('/management-portal-x99/logout/'):
                return self.get_response(request)

            # If user is authenticated and is staff/admin, grant access directly
            if request.user.is_authenticated and request.user.is_staff:
                request.session['admin_verified'] = True
                return self.get_response(request)

            # Unauthenticated users are sent to admin login
            return redirect(f'/management-portal-x99/login/?next={path}')

        return self.get_response(request)
