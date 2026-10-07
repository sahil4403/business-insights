from django.contrib.auth import get_user_model
from django.test import Client, TestCase


class CsrfFailurePageTest(TestCase):
    """CSRF 403 kabhi cryptic nahi — Hinglish help page aata hai."""

    def test_csrf_failure_renders_help(self):
        client = Client(enforce_csrf_checks=True)
        self.assertEqual(client.get('/login/').status_code, 200)
        response = client.post('/login/', {'username': 'x', 'password': 'y'})
        self.assertEqual(response.status_code, 403)
        self.assertContains(response, 'Dobara Login Karo', status_code=403)


class PdfSessionFlowTest(TestCase):
    """Login -> Labour -> Statement PDF -> back to app: session survives.

    Manual logout still works.
    """

    def test_pdf_flow_keeps_session_and_logout_works(self):
        from labour.models import Labour

        get_user_model().objects.create_user(username='pdf-flow', password='pw-12345')
        client = Client()
        response = client.post('/login/', {'username': 'pdf-flow', 'password': 'pw-12345'})
        self.assertEqual(response.status_code, 302)
        key = client.session.session_key
        self.assertIn('_auth_user_id', client.session)

        labour = Labour.objects.create(name='PDF Flow Labour')
        response = client.get(f'/labour/{labour.pk}/statement/', {'export': 'pdf'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(client.session.session_key, key)
        self.assertIn('_auth_user_id', client.session)

        response = client.get('/labour/')
        self.assertEqual(response.status_code, 200)
        self.assertIn('_auth_user_id', client.session)

        client.post('/login/logout/')
        self.assertNotIn('_auth_user_id', client.session)


class LogoutPrefetchSafetyTest(TestCase):
    """GET /login/logout/ kabhi session NA udaye.

    Root cause of "PDF ke baad automatic logout": logout GET par tha aur har
    page me GET logout link thi — browser prefetch / prerender / link-preview
    / scanner GET hit karke session uda deta tha. Sirf POST logout karta hai.
    """

    def test_get_logout_keeps_session_post_logs_out(self):
        from labour.models import Labour

        get_user_model().objects.create_user(username='logout-safe', password='pw-12345')
        client = Client()
        client.post('/login/', {'username': 'logout-safe', 'password': 'pw-12345'})
        self.assertIn('_auth_user_id', client.session)
        key = client.session.session_key

        # Prefetch simulation: GET logout -> session BACHNI chahiye
        response = client.get('/login/logout/')
        self.assertEqual(response.status_code, 302)
        self.assertEqual(client.session.session_key, key)
        self.assertIn('_auth_user_id', client.session)

        # Wapas app par — logged in rehna chahiye (PDF-return flow jaisa)
        labour = Labour.objects.create(name='Logout Safe Labour')
        response = client.get(f'/labour/{labour.pk}/statement/', {'export': 'pdf'})
        self.assertEqual(response.status_code, 200)
        self.assertIn('_auth_user_id', client.session)
        response = client.get('/labour/')
        self.assertEqual(response.status_code, 200)

        # Asli logout (POST) ab bhi kaam karta hai
        client.post('/login/logout/')
        self.assertNotIn('_auth_user_id', client.session)
