from datetime import date
from decimal import Decimal
from io import BytesIO

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from openpyxl import load_workbook

from .models import Labour, LabourAdvance, LabourExtraPayment, LabourRozi
from .views import _labour_statement_for_period, _labour_type_label


class MistriStatementTest(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.user = user_model.objects.create_user(
            username='mistri-statement-tester',
            password='test-password-123',
        )
        self.client.force_login(self.user)
        self.mistri = Labour.objects.create(
            name='Raju Bhau',
            category='MISTRI',
            sub_category='MISTRI',
            base_daily_rate=Decimal('500.00'),
            is_active=True,
            status='ACTIVE',
        )
        self.day_full = date(2026, 9, 10)
        self.day_half = date(2026, 9, 9)
        LabourRozi.objects.create(
            labour=self.mistri, date=self.day_full, day_type='FULL',
        )
        LabourRozi.objects.create(
            labour=self.mistri, date=self.day_half, day_type='HALF',
        )
        LabourExtraPayment.objects.create(
            labour=self.mistri, date=self.day_full, amount=Decimal('100.00'),
        )
        LabourAdvance.objects.create(
            labour=self.mistri, date=self.day_full, amount=Decimal('200.00'),
        )
        self.period_start = date(2026, 9, 1)
        self.period_end = date(2026, 9, 14)

    def test_statement_has_rozi_breakdown_per_day(self):
        st = _labour_statement_for_period(
            self.mistri, self.period_start, self.period_end,
        )

        rozi = st['rozi_by_date'][self.day_full]
        self.assertEqual(rozi['day_type'], 'FULL')
        self.assertEqual(rozi['day_label'], 'Full Day')
        self.assertEqual(rozi['rate'], Decimal('800'))
        self.assertEqual(rozi['amount'], Decimal('800'))

        half = st['rozi_by_date'][self.day_half]
        self.assertEqual(half['day_label'], 'Half Day')
        self.assertEqual(half['amount'], Decimal('400'))

        self.assertEqual(st['rozi_total'], Decimal('1200'))

    def test_type_label_shows_mistri_roles(self):
        self.assertEqual(_labour_type_label(self.mistri), 'Mistri')
        helper = Labour.objects.create(
            name='Helper Lal',
            category='MISTRI',
            sub_category='HELPER',
            base_daily_rate=Decimal('500.00'),
            is_active=True,
            status='ACTIVE',
        )
        self.assertEqual(_labour_type_label(helper), 'Mistri Helper')
        driver = Labour.objects.create(
            name='Gaju Bhau',
            category='HYVA_DRIVER',
            is_active=True,
            status='ACTIVE',
            is_driver=True,
        )
        self.assertEqual(_labour_type_label(driver), 'Hyva Driver')

    def test_pdf_export_works_for_mistri(self):
        response = self.client.get(
            reverse('labour:statement_export', args=[self.mistri.id]),
            {'from_date': '2026-09-01', 'to_date': '2026-09-14'},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/pdf')

    def test_excel_export_shows_day_type_rows_for_mistri(self):
        response = self.client.get(
            reverse('labour:statement_export', args=[self.mistri.id]),
            {
                'from_date': '2026-09-01',
                'to_date': '2026-09-14',
                'export': 'excel',
            },
        )

        self.assertEqual(response.status_code, 200)
        workbook = load_workbook(filename=BytesIO(response.content), read_only=True)
        values = [
            cell.value
            for row in workbook.active.iter_rows()
            for cell in row
        ]
        self.assertIn('Day Type', values)
        self.assertIn('Full Day', values)
        self.assertIn('Half Day', values)
