from datetime import timedelta
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone
from cemetery import services
from cemetery.models import Audit, Contract, Movement, Occupancy, Space
from .base import DomainFixtures


class HistoryIntegrityTests(DomainFixtures, TestCase):
    def setUp(self):
        self.create_domain_fixtures()

    def space_values(self, space, **changes):
        return {
            "code": space.code,
            "block": space.block,
            "row": space.row,
            "number": space.number,
            "kind": space.kind,
            "notes": space.notes,
            "map_x": space.map_x,
            "map_y": space.map_y,
            **changes,
        }

    def test_used_space_cannot_change_identity(self):
        with self.assertRaises(ValidationError):
            services.save_space(
                self.admin,
                self.key(),
                self.space_values(self.space, code="OTHER-SPACE", row=3),
                pk=self.space.pk,
                revision=self.space.revision,
            )
        self.space.refresh_from_db()
        self.assertEqual(self.space.code, "A-001")
        self.assertEqual(self.space.row, 1)

    def test_old_occupancies_keep_their_physical_location(self):
        services.bury(self.admin, self.key(), self.burial_data())
        Occupancy.objects.filter(space=self.space).update(ended_at=timezone.now())
        Contract.objects.filter(pk=self.contract.pk).update(state="CLOSED")
        self.space.refresh_from_db()
        with self.assertRaises(ValidationError):
            services.save_space(
                self.admin,
                self.key(),
                self.space_values(self.space, number=8),
                pk=self.space.pk,
                revision=self.space.revision,
            )

    def test_unused_space_can_correct_identity(self):
        services.save_space(
            self.admin,
            self.key(),
            self.space_values(self.destination, code="CORRECTED", row=2),
            pk=self.destination.pk,
            revision=1,
        )
        self.destination.refresh_from_db()
        self.assertEqual(self.destination.code, "CORRECTED")
        self.assertEqual(self.destination.row, 2)

    def test_used_space_can_correct_notes_and_map_with_audit(self):
        services.save_space(
            self.admin,
            self.key(),
            self.space_values(self.space, notes="Corrección documentada", map_x=250),
            pk=self.space.pk,
            revision=1,
        )
        entry = Audit.objects.get(action="space.update")
        self.assertEqual(entry.detail["previous"]["notes"], "")
        self.assertEqual(entry.detail["new"]["notes"], "Corrección documentada")
        self.assertEqual(entry.detail["new"]["map_x"], 250)

    def test_contact_correction_keeps_previous_values_in_audit(self):
        services.save_responsible(
            self.admin, self.key(), {"phone": "3009999999"}, pk=self.responsible.pk
        )
        entry = Audit.objects.get(action="responsible.update")
        self.assertEqual(entry.detail["previous"]["phone"], "3000000000")
        self.assertEqual(entry.detail["new"]["phone"], "3009999999")

    def test_transfer_request_rechecks_destination_in_transaction(self):
        burial = services.bury(self.admin, self.key(), self.burial_data())
        target_contract = Contract.objects.create(
            number="C-DEST",
            space=self.destination,
            responsible=self.responsible,
            amount=100,
            starts_on=self.today,
            ends_on=self.today + timedelta(days=30),
            terms="Prueba",
        )
        # El formulario se abrió antes de que otro usuario marcara mantenimiento.
        stale_destination = Space.objects.get(pk=self.destination.pk)
        Space.objects.filter(pk=self.destination.pk).update(condition="MAINTENANCE")
        with self.assertRaises(ValidationError):
            services.request_movement(
                self.admin,
                self.key(),
                {
                    "occupancy": Occupancy.objects.get(pk=burial["id"]),
                    "kind": "TRANSFER",
                    "destination": stale_destination,
                    "destination_contract": target_contract,
                    "external_destination": "",
                    "reason": "Prueba",
                    "proposed_on": self.today,
                },
            )
        self.assertFalse(Movement.objects.exists())

    def test_audit_details_are_available_only_to_administration(self):
        services.save_responsible(
            self.admin, self.key(), {"phone": "3009999999"}, pk=self.responsible.pk
        )
        entry = Audit.objects.get(action="responsible.update")
        for actor in (self.viewer, self.office, self.treasury, self.operator):
            self.client.force_login(actor)
            self.assertEqual(
                self.client.get(f"/auditoria/{entry.pk}/").status_code, 403
            )
        self.client.force_login(self.admin)
        response = self.client.get(f"/auditoria/{entry.pk}/")
        self.assertContains(response, "3000000000")
        self.assertContains(response, "3009999999")
        self.assertEqual(self.client.post(f"/auditoria/{entry.pk}/").status_code, 405)

    def test_password_changes_never_enter_audit_details(self):
        password = "Distinct-synthetic-secret-9128!"
        services.save_user(
            self.admin,
            self.key(),
            {
                "email": "audit@example.test",
                "first_name": "Example",
                "last_name": "",
                "role": "VIEWER",
                "is_active": True,
                "password": password,
            },
        )
        entry = Audit.objects.get(action="user.create")
        self.assertNotIn(password, str(entry.detail))
        self.assertNotIn("password", str(entry.detail))

    def test_used_space_form_protects_identity_fields(self):
        self.client.force_login(self.admin)
        response = self.client.get(f"/gestion/sepulturas/{self.space.pk}/editar/")
        self.assertTrue(response.context["form"].fields["code"].disabled)
        self.assertTrue(response.context["form"].fields["block"].disabled)
        self.assertFalse(response.context["form"].fields["notes"].disabled)
