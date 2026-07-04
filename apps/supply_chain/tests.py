from django.test import TestCase
from django.urls import reverse


class SupplyChainAppSmokeTests(TestCase):
    def test_dashboard_route_exists(self):
        response = self.client.get(reverse('supply_chain:dashboard'))
        self.assertNotEqual(response.status_code, 404)
