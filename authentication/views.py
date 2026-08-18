from django.contrib.auth import logout
from django.contrib.auth.views import LoginView
from django.http import HttpResponse
from django.shortcuts import redirect
from django.views import View

from core.rate_limit import (
    login_rate_limit_check,
    record_login_failure,
    clear_login_rate_limit,
)


class UserLoginView(LoginView):
    template_name = 'authentication/login.html'
    redirect_authenticated_user = True
    next_page = '/'

    def post(self, request, *args, **kwargs):
        allowed, retry_after = login_rate_limit_check(request, 'user_login')
        if not allowed:
            return HttpResponse(
                f'Too many login attempts. Please try again in {max(1, retry_after // 60)} minute(s).',
                status=429,
            )

        response = super().post(request, *args, **kwargs)

        if request.user.is_authenticated:
            clear_login_rate_limit(request, 'user_login')
        else:
            record_login_failure(request, 'user_login')

        return response


class UserLogoutView(View):
    def get(self, request, *args, **kwargs):
        logout(request)
        return redirect('/login/')

    def post(self, request, *args, **kwargs):
        logout(request)
        return redirect('/login/')
