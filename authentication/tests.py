from django.test import Client, TestCase


class CsrfFailurePageTest(TestCase):
    """CSRF 403 kabhi cryptic nahi — Hinglish help page aata hai."""

    def test_csrf_failure_renders_help(self):
        client = Client(enforce_csrf_checks=True)
        self.assertEqual(client.get('/login/').status_code, 200)
        response = client.post('/login/', {'username': 'x', 'password': 'y'})
        self.assertEqual(response.status_code, 403)
        self.assertContains(response, 'Dobara Login Karo', status_code=403)
