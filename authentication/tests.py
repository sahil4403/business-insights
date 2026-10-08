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


class ViewerRoleTest(TestCase):
    """Read-only viewer (Raj): sab dekh sakta hai, kuch badal nahi sakta.

    Backend: ViewerReadOnlyMiddleware har unsafe POST/PUT/PATCH/DELETE par
    403 deta hai. UI: write buttons hidden. Admins unaffected.
    """

    def setUp(self):
        from django.core.management import call_command

        from labour.models import Labour

        call_command('create_viewer')
        call_command('create_viewer')  # dobara: duplicate nahi banna chahiye
        self.assertEqual(
            get_user_model().objects.filter(username='Raj').count(), 1
        )
        self.viewer = get_user_model().objects.get(username='Raj')
        self.assertTrue(self.viewer.check_password('0707'))
        self.assertTrue(self.viewer.password.startswith('pbkdf2_sha256$'))

        self.admin = get_user_model().objects.create_superuser(
            username='viewer-admin', password='pw-12345',
            email='a@test.local',
        )
        self.labour = Labour.objects.create(
            name='Viewer Test Labour', category='TRACTOR',
            is_active=True, status='ACTIVE',
        )
        self.vclient = Client()
        self.assertEqual(
            self.vclient.post(
                '/login/', {'username': 'Raj', 'password': '0707'}
            ).status_code, 302,
        )
        self.aclient = Client()
        self.aclient.force_login(self.admin)

    def test_viewer_reads_everything(self):
        for url in ('/', '/trips/', '/labour/',
                    f'/labour/{self.labour.pk}/',
                    f'/labour/category/{self.labour.category}/',
                    '/expenses/', '/expenses/list/',
                    '/reports/payments/', '/reports/vehicles/',
                    '/reports/customers/'):
            with self.subTest(url=url):
                self.assertEqual(self.vclient.get(url).status_code, 200)

    def test_viewer_exports_allowed(self):
        self.assertEqual(
            self.vclient.get('/trips/', {'export': 'excel'}).status_code, 200
        )
        self.assertEqual(
            self.vclient.get(
                f'/labour/{self.labour.pk}/statement/', {'export': 'pdf'}
            ).status_code, 200,
        )

    def test_viewer_writes_blocked_403(self):
        post_urls = [
            '/trips/add/', '/trips/create/',
            '/reports/payments/add/',
            '/customers/quick-add/',
            '/labour/add/', '/labour/trips/add/',
            '/labour/hyva/trips/add/', '/labour/jcb/trips/add/',
            '/labour/extras/add/', '/labour/advances/add/',
            '/labour/rozi/add/', '/labour/rozi/quick/',
            '/labour/advances/quick/',
            '/labour/driver-payment/add/',
            f'/labour/{self.labour.pk}/settle/',
            f'/labour/{self.labour.pk}/outstanding/set/',
            '/expenses/add/', '/staff/',
        ]
        for url in post_urls:
            with self.subTest(url=url):
                self.assertEqual(self.vclient.post(url, {}).status_code, 403)
        # Admin portal: viewer staff nahi -> redirect (koi access nahi)
        self.assertEqual(
            self.vclient.post('/management-portal-x99/').status_code, 302
        )
        # Login/logout POST viewer ke liye khula rehta hai
        self.assertEqual(
            self.vclient.post('/login/logout/').status_code, 302
        )

    def test_viewer_ui_hides_write_buttons(self):
        filtered = {'from_date': '2026-01-01', 'to_date': '2026-12-31'}
        dashboard = self.vclient.get('/', filtered).content.decode()
        self.assertNotIn('Add New Trip', dashboard)
        trip_list = self.vclient.get('/trips/').content.decode()
        self.assertNotIn('＋ Add Trip', trip_list)
        self.assertNotIn('/trips/add/', trip_list)
        labour_page = self.vclient.get('/labour/').content.decode()
        self.assertNotIn('Add Labour', labour_page)
        detail = self.vclient.get(
            f'/labour/{self.labour.pk}/').content.decode()
        self.assertNotIn('Settle Now', detail)
        self.assertNotIn('/labour/extras/add/', detail)
        self.assertNotIn('/labour/advances/add/', detail)
        self.assertNotIn('Add Rozi', detail)

    def test_admin_unchanged(self):
        filtered = {'from_date': '2026-01-01', 'to_date': '2026-12-31'}
        dashboard = self.aclient.get('/', filtered).content.decode()
        self.assertIn('Add New Trip', dashboard)
        trip_list = self.aclient.get('/trips/').content.decode()
        self.assertIn('＋ Add Trip', trip_list)
        # Admin ka add-form GET ab bhi khulta hai (poora behavior baaki
        # existing suite se covered hai)
        self.assertEqual(
            self.aclient.get('/trips/add/').status_code, 200
        )
