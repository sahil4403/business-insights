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


# ============================================================
# STAFF MANAGEMENT (Superuser Only)
# ============================================================
import logging

from django.contrib import messages
from django.contrib.auth import get_user_model, update_session_auth_hash
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.sessions.models import Session
from django.shortcuts import get_object_or_404, redirect, render

logger = logging.getLogger('trips')

User = get_user_model()


def _force_logout_all_devices(user, keep_session_key=None):
    """
    User ki SAARI sessions delete karo (sab phones/computers logout).
    Password change / deactivate par turant call hota hai.
    Option A: keep_session_key diya toh wo session bacha rehta hai
    (admin apna password change kare toh current device logged-in rahe).
    """
    count = 0
    for session in Session.objects.iterator():
        try:
            data = session.get_decoded()
        except Exception:
            continue
        if data.get('_auth_user_id') == str(user.id):
            if keep_session_key and session.session_key == keep_session_key:
                continue
            session.delete()
            count += 1
    return count


@login_required(login_url='/login/')
@user_passes_test(lambda u: u.is_superuser, login_url='/login/')
def staff_manage(request):
    staff_list = User.objects.all().order_by('-is_active', 'username')

    if request.method == 'POST':
        action = request.POST.get('action')

        # ---------------- ADD NEW STAFF ----------------
        if action == 'add_staff':
            username = request.POST.get('username', '').strip()
            first_name = request.POST.get('first_name', '').strip()
            password = request.POST.get('password', '')
            confirm = request.POST.get('confirm_password', '')

            errors = []
            if not username:
                errors.append('Username required hai.')
            elif User.objects.filter(username__iexact=username).exists():
                errors.append(f'"{username}" username pehle se exist karta hai.')
            if len(password) < 6:
                errors.append('Password kam se kam 6 characters ka hona chahiye.')
            if password != confirm:
                errors.append('Password aur Confirm Password match nahi kar rahe.')

            if errors:
                messages.error(request, ' '.join(errors))
            else:
                User.objects.create_user(
                    username=username,
                    password=password,
                    first_name=first_name,
                    is_staff=True,
                )
                logger.info('Staff CREATED | username=%s | by=%s', username, request.user.username)
                messages.success(request, f'Staff "{username}" create ho gaya!')

        # ---------------- RESET PASSWORD ----------------
        elif action == 'reset_password':
            target = get_object_or_404(User, pk=request.POST.get('user_id'))
            password = request.POST.get('password', '')
            confirm = request.POST.get('confirm_password', '')

            errors = []
            if len(password) < 6:
                errors.append('Password kam se kam 6 characters ka hona chahiye.')
            if password != confirm:
                errors.append('Password aur Confirm Password match nahi kar rahe.')

            if errors:
                messages.error(request, ' '.join(errors))
            else:
                is_self = (target.pk == request.user.pk)
                target.set_password(password)
                target.save()

                # OPTION A: admin khud change kare toh current device session bachi rahe
                keep = request.session.session_key if is_self else None
                killed = _force_logout_all_devices(target, keep_session_key=keep)

                if is_self:
                    # IMPORTANT: target (naye password wala instance) pass karo,
                    # request.user nahi — warna PURANA hash session me jayega
                    update_session_auth_hash(request, target)

                logger.info(
                    'Password RESET | user=%s | by=%s | devices_logged_out=%s',
                    target.username, request.user.username, killed,
                )
                if is_self:
                    messages.success(
                        request,
                        f'Password updated! Aapka current device logged-in hai, '
                        f'{killed} doosre device(s) logout ho gaye.'
                    )
                else:
                    messages.success(
                        request,
                        f'{target.username} ka password change ho gaya! '
                        f'Uske {killed} device(s) se logout kar diya gaya.'
                    )

        # ---------------- ACTIVATE / DEACTIVATE ----------------
        elif action == 'toggle_active':
            target = get_object_or_404(User, pk=request.POST.get('user_id'))
            if target.pk == request.user.pk:
                messages.error(request, 'Aap khud ko deactivate nahi kar sakte.')
            else:
                target.is_active = not target.is_active
                target.save()
                if not target.is_active:
                    killed = _force_logout_all_devices(target)
                    logger.info(
                        'Staff DEACTIVATED | user=%s | by=%s | devices_logged_out=%s',
                        target.username, request.user.username, killed,
                    )
                    messages.success(
                        request,
                        f'{target.username} deactivated! Uske {killed} device(s) se '
                        f'logout kar diya gaya.'
                    )
                else:
                    logger.info('Staff ACTIVATED | user=%s | by=%s', target.username, request.user.username)
                    messages.success(request, f'{target.username} activated!')

        return redirect('staff_manage')

    context = {
        'staff_list': staff_list,
        'active_sessions': Session.objects.count(),
    }
    return render(request, 'authentication/staff_manage.html', context)
