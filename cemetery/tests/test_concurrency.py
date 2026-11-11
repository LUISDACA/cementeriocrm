from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from unittest import skipUnless
from threading import Barrier
from django.core.exceptions import ValidationError
from django.db import close_old_connections, connection, connections
from django.test import TransactionTestCase, override_settings
from cemetery import services
from cemetery.models import Occupancy, Payment, PersonResponsible, User
from .base import DomainFixtures


@override_settings(
    PASSWORD_HASHERS=["django.contrib.auth.hashers.PBKDF2PasswordHasher"]
)
@skipUnless(
    connection.vendor == "postgresql", "Requiere concurrencia real en PostgreSQL"
)
class ConcurrencyTests(DomainFixtures, TransactionTestCase):
    def setUp(self):
        self.create_domain_fixtures()

    def race(self, callback):
        barrier = Barrier(2)

        def worker(index):
            close_old_connections()
            try:
                actor = User.objects.get(pk=self.admin.pk)
                barrier.wait(timeout=10)
                try:
                    callback(actor, index)
                    return "ok"
                except ValidationError:
                    return "rejected"
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = [executor.submit(worker, i) for i in range(2)]
            return [future.result(timeout=30) for future in futures]

    def test_two_burials_compete_for_one_space(self):
        PersonResponsible.objects.create(
            person=self.other_person,
            responsible=self.responsible,
            relationship="Familiar",
        )
        results = self.race(
            lambda actor, i: services.bury(
                actor,
                self.key(),
                self.burial_data(person=self.person if i == 0 else self.other_person),
            )
        )
        self.assertCountEqual(results, ["ok", "rejected"])
        self.assertEqual(Occupancy.objects.filter(ended_at__isnull=True).count(), 1)

    def test_two_payments_cannot_overdraw_balance(self):
        results = self.race(
            lambda actor, i: services.record_payment(
                actor,
                self.key(),
                self.payment_data(amount=Decimal("700.00"), reference=f"RACE-{i}"),
            )
        )
        self.assertCountEqual(results, ["ok", "rejected"])
        self.assertEqual(Payment.objects.count(), 1)
        self.assertEqual(self.contract.balance, Decimal("300.00"))

    def test_duplicate_request_from_two_workers_creates_one_payment(self):
        key, data = self.key(), self.payment_data()
        results = self.race(lambda actor, i: services.record_payment(actor, key, data))
        self.assertEqual(results, ["ok", "ok"])
        self.assertEqual(Payment.objects.count(), 1)
