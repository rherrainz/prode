from django.test import TestCase, override_settings
from django.urls import reverse


class HomeRoutingTests(TestCase):
    def test_home_renders(self):
        response = self.client.get(reverse('home'))

        self.assertEqual(response.status_code, 200)

    @override_settings(DEBUG=False)
    def test_unknown_url_redirects_to_home(self):
        response = self.client.get('/ruta-que-no-existe/')

        self.assertRedirects(response, reverse('home'))
