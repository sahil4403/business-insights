from django.shortcuts import redirect


class OperatorAccessMiddleware:
    """
    Restricted operator mode — a non-superuser login linked to a Labour
    (Labour.user) sees ONLY his own detail page + JCB loading add/edit.
    Everything else redirects to his own page. Data is shared, so admin
    sees operator entries normally. Superusers and unlinked users pass
    through untouched. Also stamps request.is_operator / operator_labour
    for templates and views.
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.is_operator = False
        request.operator_labour = None

        user = getattr(request, 'user', None)
        if user and user.is_authenticated and not user.is_superuser:
            from labour.models import Labour
            try:
                lab = user.operator_labour
            except Labour.DoesNotExist:
                lab = None
            if lab is not None:
                request.is_operator = True
                request.operator_labour = lab
                if not self._allowed(request.path, lab.id):
                    return redirect(f'/labour/{lab.id}/')

        return self.get_response(request)

    def _allowed(self, path, lab_id):
        if path in ('/login/', '/login/logout/', '/favicon.ico'):
            return True
        if path.startswith('/static/') or path.startswith('/media/'):
            return True
        if path == f'/labour/{lab_id}/':
            return True
        if path == '/labour/jcb/trips/add/':
            return True
        if path.startswith('/labour/jcb/trips/edit/'):
            return True  # ownership of the entry is enforced in the view
        if path in (f'/labour/extras/add/{lab_id}/', f'/labour/advances/add/{lab_id}/',
                      f'/labour/holidays/add/{lab_id}/', f'/labour/{lab_id}/outstanding/set/'):
            return True
        if path.startswith((
            '/labour/extras/edit/', '/labour/extras/delete/',
            '/labour/advances/edit/', '/labour/advances/delete/',
            '/labour/holidays/delete/',
        )):
            return True  # ownership of the entry is enforced in the view
        return False


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
