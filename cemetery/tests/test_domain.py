from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch
from unittest import skipUnless
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import DatabaseError, IntegrityError, connection, transaction
from django.test import TestCase, override_settings
from django.utils import timezone
from cemetery import services
from cemetery.models import (
    Audit,
    Command,
    Contract,
    Event,
    Movement,
    Occupancy,
    Payment,
    Person,
    Reservation,
    User,
)
from .base import DomainFixtures


class DomainTests(DomainFixtures, TestCase):
    def setUp(self):
        self.create_domain_fixtures()

    def test_one_person_per_space(self):
        services.bury(self.admin, self.key(), self.burial_data())
        with self.assertRaises(ValidationError):
            services.bury(
                self.admin, self.key(), self.burial_data(person=self.other_person)
            )
        self.assertEqual(
            Occupancy.objects.filter(space=self.space, ended_at__isnull=True).count(), 1
        )

    def test_same_person_cannot_occupy_two_spaces(self):
        services.bury(self.admin, self.key(), self.burial_data())
        c2 = self.make_destination_contract()
        with self.assertRaises(ValidationError):
            services.bury(
                self.admin,
                self.key(),
                self.burial_data(space=self.destination, contract=c2),
            )

    def test_burial_requires_matching_contract(self):
        with self.assertRaises(ValidationError):
            services.bury(
                self.admin, self.key(), self.burial_data(space=self.destination)
            )
        self.assertFalse(Occupancy.objects.exists())

    def test_burial_rejects_expired_contract(self):
        self.contract.ends_on = self.today - timedelta(days=20)
        self.contract.save()
        with self.assertRaises(ValidationError):
            services.bury(self.admin, self.key(), self.burial_data())

    def test_burial_requires_linked_responsible(self):
        self.contract.responsible = self.other_responsible
        self.contract.save()
        with self.assertRaises(ValidationError):
            services.bury(self.admin, self.key(), self.burial_data())

    def test_burial_rejects_date_before_death(self):
        with self.assertRaises(ValidationError):
            services.bury(
                self.admin,
                self.key(),
                self.burial_data(occurred_at=timezone.now() - timedelta(days=100)),
            )

    def test_burial_retry_does_not_duplicate(self):
        key, data = self.key(), self.burial_data()
        first = services.bury(self.admin, key, data)
        self.assertEqual(first, services.bury(self.admin, key, data))
        self.assertEqual(Occupancy.objects.count(), 1)
        self.assertEqual(Event.objects.filter(kind="BURIAL").count(), 1)

    def test_idempotency_rejects_payload_change(self):
        key, data = self.key(), self.payment_data()
        services.record_payment(self.admin, key, data)
        with self.assertRaises(ValidationError):
            services.record_payment(
                self.admin, key, {**data, "amount": Decimal("301.00")}
            )

    def test_authorization_is_rechecked_on_retry(self):
        key, data = self.key(), self.payment_data()
        services.record_payment(self.treasury, key, data)
        User.objects.filter(pk=self.treasury.pk).update(role="VIEWER")
        with self.assertRaises(PermissionDenied):
            services.record_payment(self.treasury, key, data)

    def test_burial_failure_rolls_back_occupancy(self):
        with patch(
            "cemetery.services.event", side_effect=RuntimeError("Fallo de prueba")
        ):
            with self.assertRaises(RuntimeError):
                services.bury(self.admin, self.key(), self.burial_data())
        self.assertFalse(Occupancy.objects.exists())
        self.assertFalse(Command.objects.exists())
        self.space.refresh_from_db()
        self.assertEqual(self.space.status, "AVAILABLE")

    def test_database_prevents_two_current_occupancies(self):
        Occupancy.objects.create(
            space=self.space,
            person=self.person,
            contract=self.contract,
            started_at=timezone.now(),
        )
        with self.assertRaises(IntegrityError), transaction.atomic():
            Occupancy.objects.create(
                space=self.space,
                person=self.other_person,
                contract=self.contract,
                started_at=timezone.now(),
            )

    def test_contract_expiry_never_releases_space(self):
        services.bury(self.admin, self.key(), self.burial_data())
        self.contract.ends_on = self.today - timedelta(days=1)
        self.contract.save()
        self.space.refresh_from_db()
        self.assertEqual(self.space.status, "OCCUPIED")

    def test_administrative_change_cannot_release_occupied_space(self):
        services.bury(self.admin, self.key(), self.burial_data())
        self.space.refresh_from_db()
        with self.assertRaises(ValidationError):
            services.change_condition(
                self.admin,
                self.key(),
                self.space.pk,
                "AVAILABLE",
                "Intento",
                self.space.revision,
            )

    def test_optimistic_revision_rejects_stale_changes(self):
        services.change_condition(
            self.admin, self.key(), self.destination.pk, "MAINTENANCE", "Revisión", 1
        )
        with self.assertRaises(ValidationError):
            services.change_condition(
                self.admin, self.key(), self.destination.pk, "AVAILABLE", "Reabrir", 1
            )

    def test_payment_retry_and_balance(self):
        key, data = self.key(), self.payment_data()
        services.record_payment(self.treasury, key, data)
        services.record_payment(self.treasury, key, data)
        self.assertEqual(self.contract.balance, Decimal("700.00"))
        self.assertEqual(Payment.objects.count(), 1)

    def test_overpayment_rejected(self):
        with self.assertRaises(ValidationError):
            services.record_payment(
                self.admin, self.key(), self.payment_data(amount=Decimal("1000.01"))
            )
        self.assertFalse(Payment.objects.exists())

    def test_money_rejects_negative_nan_and_fractional_cents(self):
        for value in ("0", "-1", "NaN", "Infinity", "0.001", "1000000000000"):
            with self.subTest(value=value), self.assertRaises(ValidationError):
                services.money(value)

    def test_void_keeps_original_and_restores_balance(self):
        result = services.record_payment(self.admin, self.key(), self.payment_data())
        services.void_payment(
            self.admin, self.key(), result["id"], "Registro equivocado"
        )
        self.assertEqual(self.contract.balance, Decimal("1000.00"))
        self.assertEqual(Payment.objects.count(), 1)
        self.assertIsNotNone(Payment.objects.get().voided_at)

    def test_office_cannot_record_payments(self):
        with self.assertRaises(PermissionDenied):
            services.record_payment(self.office, self.key(), self.payment_data())

    def test_reservation_requires_deposit(self):
        with self.assertRaises(ValidationError):
            services.create_reservation(
                self.admin, self.key(), self.reservation_data(amount=0)
            )
        self.assertFalse(Reservation.objects.exists())
        self.assertFalse(Payment.objects.exists())

    def test_paid_reservation_blocks_other_responsible(self):
        services.create_reservation(self.admin, self.key(), self.reservation_data())
        with self.assertRaises(ValidationError):
            services.create_contract(
                self.admin,
                self.key(),
                self.contract_data(responsible=self.other_responsible),
            )

    def test_deposit_is_credited_once_on_contract(self):
        services.create_reservation(self.admin, self.key(), self.reservation_data())
        key, data = self.key(), self.contract_data()
        result = services.create_contract(self.admin, key, data)
        services.create_contract(self.admin, key, data)
        contract = Contract.objects.get(pk=result["id"])
        self.assertEqual(contract.paid, Decimal("100.00"))
        self.assertEqual(contract.balance, Decimal("900.00"))
        self.assertEqual(Payment.objects.count(), 1)
        self.assertEqual(Reservation.objects.get().state, "CONSUMED")

    def test_cancel_reservation_preserves_payment(self):
        result = services.create_reservation(
            self.admin, self.key(), self.reservation_data()
        )
        services.cancel_reservation(
            self.admin, self.key(), result["id"], "Cancelación solicitada"
        )
        self.assertEqual(Payment.objects.count(), 1)
        self.assertIsNone(Payment.objects.get().voided_at)
        self.destination.refresh_from_db()
        self.assertEqual(self.destination.status, "AVAILABLE")

    def test_expired_reservation_is_available_without_deleting_payment(self):
        result = services.create_reservation(
            self.admin, self.key(), self.reservation_data()
        )
        Reservation.objects.filter(pk=result["id"]).update(
            expires_on=self.today - timedelta(days=1)
        )
        self.destination.refresh_from_db()
        self.assertEqual(self.destination.status, "AVAILABLE")
        services.create_reservation(
            self.admin,
            self.key(),
            self.reservation_data(responsible=self.other_responsible),
        )
        self.assertEqual(Reservation.objects.filter(state="EXPIRED").count(), 1)
        self.assertEqual(Payment.objects.count(), 2)

    def test_last_admin_cannot_be_disabled(self):
        data = {
            "email": self.admin.email,
            "first_name": "Admin",
            "last_name": "",
            "role": "ADMIN",
            "is_active": False,
            "password": "",
        }
        with self.assertRaises(ValidationError):
            services.save_user(self.admin, self.key(), data, pk=self.admin.pk)
        self.admin.refresh_from_db()
        self.assertTrue(self.admin.is_active)

    def test_password_is_hashed(self):
        data = {
            "email": "New@Example.test",
            "first_name": "Nueva",
            "last_name": "",
            "role": "VIEWER",
            "is_active": True,
            "password": "Unrelated-secret-7843!",
        }
        result = services.save_user(self.admin, self.key(), data)
        user = User.objects.get(pk=result["id"])
        self.assertEqual(user.email, "new@example.test")
        self.assertNotEqual(user.password, data["password"])
        self.assertTrue(user.check_password(data["password"]))

    def test_email_case_duplicates_rejected_by_database(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            User.objects.create_user("ADMIN@EXAMPLE.TEST", "secret", role="VIEWER")

    @skipUnless(connection.vendor == "postgresql", "Requiere triggers de PostgreSQL")
    def test_history_and_audit_are_immutable(self):
        services.change_condition(
            self.admin, self.key(), self.destination.pk, "MAINTENANCE", "Revisión", 1
        )
        for model in (Event, Audit):
            with (
                self.subTest(model=model.__name__),
                self.assertRaises(DatabaseError),
                transaction.atomic(),
            ):
                model.objects.all().delete()

    def make_destination_contract(self):
        return Contract.objects.create(
            number="C002",
            space=self.destination,
            responsible=self.responsible,
            amount=Decimal("1000.00"),
            starts_on=self.today - timedelta(days=90),
            ends_on=self.today + timedelta(days=90),
            terms="Contrato de destino",
        )

    def contract_data(self, **overrides):
        return {
            "number": "C002",
            "space": self.destination,
            "responsible": self.responsible,
            "amount": Decimal("1000.00"),
            "starts_on": self.today,
            "ends_on": self.today + timedelta(days=90),
            "terms": "Condiciones",
            **overrides,
        }

    def requested_movement(self, kind="TRANSFER"):
        result = services.bury(self.admin, self.key(), self.burial_data())
        contract = self.make_destination_contract() if kind == "TRANSFER" else None
        data = {
            "occupancy": Occupancy.objects.get(pk=result["id"]),
            "kind": kind,
            "destination": self.destination if contract else None,
            "destination_contract": contract,
            "external_destination": "" if contract else "Destino externo autorizado",
            "reason": "Solicitud de prueba",
            "proposed_on": self.today,
        }
        result = services.request_movement(self.admin, self.key(), data)
        return Movement.objects.get(pk=result["id"])

    def test_movement_request_does_not_release_space(self):
        self.requested_movement()
        self.space.refresh_from_db()
        self.assertEqual(self.space.status, "OCCUPIED")

    @override_settings(CEMETERY_MOVEMENTS_APPROVED=False)
    def test_pending_operating_rules_block_authorization(self):
        movement = self.requested_movement()
        with self.assertRaises(ValidationError):
            services.movement_action(
                self.admin,
                self.key(),
                movement.pk,
                "authorize",
                document_reference="DOC-1",
            )

    @override_settings(CEMETERY_MOVEMENTS_APPROVED=True)
    def test_transfer_changes_origin_destination_and_history(self):
        movement = self.requested_movement()
        services.movement_action(
            self.admin, self.key(), movement.pk, "authorize", document_reference="DOC-1"
        )
        key = self.key()
        services.movement_action(self.operator, key, movement.pk, "execute")
        services.movement_action(self.operator, key, movement.pk, "execute")
        self.space.refresh_from_db()
        self.destination.refresh_from_db()
        self.assertEqual(self.space.status, "AVAILABLE")
        self.assertEqual(self.destination.status, "OCCUPIED")
        self.assertEqual(
            Occupancy.objects.filter(person=self.person, ended_at__isnull=True).count(),
            1,
        )
        self.assertEqual(Occupancy.objects.filter(person=self.person).count(), 2)
        self.assertEqual(Event.objects.filter(kind="TRANSFER_IN").count(), 1)

    @override_settings(CEMETERY_MOVEMENTS_APPROVED=True)
    def test_transfer_rollback_keeps_original_location(self):
        movement = self.requested_movement()
        services.movement_action(
            self.admin, self.key(), movement.pk, "authorize", document_reference="DOC-1"
        )
        with patch(
            "cemetery.services.event", side_effect=RuntimeError("Fallo simulado")
        ):
            with self.assertRaises(RuntimeError):
                services.movement_action(self.admin, self.key(), movement.pk, "execute")
        current = Occupancy.objects.get(person=self.person, ended_at__isnull=True)
        self.assertEqual(current.space_id, self.space.pk)
        movement.refresh_from_db()
        self.assertEqual(movement.state, "AUTHORIZED")

    @override_settings(CEMETERY_MOVEMENTS_APPROVED=True)
    def test_transfer_revalidates_destination_at_execution(self):
        movement = self.requested_movement()
        services.movement_action(
            self.admin, self.key(), movement.pk, "authorize", document_reference="DOC-1"
        )
        services.change_condition(
            self.admin,
            self.key(),
            self.destination.pk,
            "MAINTENANCE",
            "Intervención",
            1,
        )
        with self.assertRaises(ValidationError):
            services.movement_action(self.admin, self.key(), movement.pk, "execute")
        self.assertTrue(
            Occupancy.objects.filter(space=self.space, ended_at__isnull=True).exists()
        )

    @override_settings(CEMETERY_MOVEMENTS_APPROVED=True)
    def test_exhumation_releases_only_after_authorized_execution(self):
        movement = self.requested_movement(kind="EXHUMATION")
        with self.assertRaises(ValidationError):
            services.movement_action(self.operator, self.key(), movement.pk, "execute")
        services.movement_action(
            self.admin, self.key(), movement.pk, "authorize", document_reference="DOC-2"
        )
        services.movement_action(self.operator, self.key(), movement.pk, "execute")
        self.assertFalse(Occupancy.objects.filter(ended_at__isnull=True).exists())

    def test_homonyms_without_identification_are_allowed(self):
        self.assertEqual(
            Person.objects.filter(first_name="María", last_name="Prueba").count(), 2
        )

    def test_invalid_person_dates_rejected(self):
        with self.assertRaises(ValidationError):
            services.save_person(
                self.admin,
                self.key(),
                {
                    "first_name": "A",
                    "last_name": "B",
                    "death_date": self.today + timedelta(days=1),
                    "birth_date": None,
                    "identification": "",
                    "notes": "",
                },
            )
