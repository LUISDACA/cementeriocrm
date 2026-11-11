from datetime import timedelta
from django.test import TestCase, override_settings
from cemetery import services
from cemetery.models import Block, Contract, Movement, Occupancy, Zone
from .base import DomainFixtures


class RegistrySearchTests(DomainFixtures, TestCase):
    def setUp(self):
        self.create_domain_fixtures()
        self.client.force_login(self.admin)

    def test_zone_search_filters_the_catalog(self):
        zone = Zone.objects.create(name="Sector norte")
        response = self.client.get("/gestion/zonas/", {"q": "norte"})
        self.assertEqual(list(response.context["page"]), [zone])

    def test_block_search_accepts_its_zone_name(self):
        zone = Zone.objects.create(name="Sector norte")
        block = Block.objects.create(zone=zone, name="Bloque nuevo")
        response = self.client.get("/gestion/bloques/", {"q": "norte"})
        self.assertEqual(list(response.context["page"]), [block])

    def test_contract_search_accepts_its_responsible_name(self):
        response = self.client.get("/gestion/contratos/", {"q": self.responsible.name})
        self.assertEqual(list(response.context["page"]), [self.contract])

    def test_user_search_accepts_full_name(self):
        self.office.first_name, self.office.last_name = "Lucía", "Montes"
        self.office.save()
        response = self.client.get("/gestion/usuarios/", {"q": "Lucía   Montes"})
        self.assertEqual(list(response.context["page"]), [self.office])

    def test_movement_search_accepts_first_and_full_name(self):
        burial = services.bury(self.admin, self.key(), self.burial_data())
        movement = Movement.objects.create(
            occupancy=Occupancy.objects.get(pk=burial["id"]),
            kind="EXHUMATION",
            reason="Demostración",
            external_destination="Destino ficticio",
            proposed_on=self.today,
            requested_by=self.admin,
        )
        for term in ("María", "María Prueba", self.space.code):
            with self.subTest(term=term):
                response = self.client.get("/gestion/movimientos/", {"q": term})
                self.assertEqual(list(response.context["page"]), [movement])


@override_settings(CEMETERY_EXPIRY_DAYS=30)
class ContractDateTests(DomainFixtures, TestCase):
    def setUp(self):
        self.create_domain_fixtures()
        self.client.force_login(self.admin)

    def test_validity_and_remaining_days_cover_inclusive_boundaries(self):
        for starts, ends, validity, label in (
            (-10, -1, "Vencido", "Venció hace 1 día"),
            (-10, 0, "Próximo a vencer", "Vence hoy"),
            (0, 1, "Próximo a vencer", "1 día"),
            (0, 30, "Próximo a vencer", "30 días"),
            (0, 31, "Vigente", "31 días"),
            (1, 31, "Pendiente de inicio", "31 días"),
        ):
            with self.subTest(ends=ends, starts=starts):
                self.contract.starts_on = self.today + timedelta(days=starts)
                self.contract.ends_on = self.today + timedelta(days=ends)
                self.assertEqual(self.contract.validity, validity)
                self.assertEqual(self.contract.days_remaining, ends)
                self.assertEqual(self.contract.expiry_label, label)

    def test_closed_contract_has_no_remaining_term(self):
        self.contract.state = Contract.State.CLOSED
        self.assertIsNone(self.contract.days_remaining)
        self.assertEqual(self.contract.expiry_label, "No aplica")

    def test_list_and_detail_show_deadline_and_both_dates(self):
        self.contract.ends_on = self.today
        self.contract.save()
        response = self.client.get("/gestion/contratos/")
        self.assertContains(response, "Plazo restante")
        self.assertContains(response, "Inicio")
        self.assertContains(response, "Vence hoy")
        response = self.client.get(f"/contrato/{self.contract.pk}/")
        self.assertContains(response, "Vence hoy")

    def test_expired_and_soon_filters_respect_today(self):
        for delta in (-1, 0, 30, 31):
            self.contract.ends_on = self.today + timedelta(days=delta)
            self.contract.save()
            with self.subTest(delta=delta):
                expired = self.client.get(
                    "/gestion/contratos/", {"validity": "expired"}
                )
                soon = self.client.get("/gestion/contratos/", {"validity": "soon"})
                self.assertEqual(
                    expired.context["page"].paginator.count, int(delta < 0)
                )
                self.assertEqual(
                    soon.context["page"].paginator.count, int(0 <= delta <= 30)
                )
