from django.test import RequestFactory, TestCase
from cemetery import services
from cemetery.models import Event, Person, Space
from cemetery.queries import space_counts, spaces
from cemetery.views import map_data
from .base import DomainFixtures


class QueryTests(DomainFixtures, TestCase):
    def setUp(self):
        self.create_domain_fixtures()
        self.client.force_login(self.admin)

    def test_invalid_numeric_filters_do_not_cause_server_errors(self):
        for value in ("not-a-number", "-1", "9" * 5000, "9223372036854775808", "١"):
            with self.subTest(value=value[:30]):
                self.assertEqual(
                    self.client.get("/mapa/datos/", {"block": value}).status_code, 400
                )
                response = self.client.get("/gestion/sepulturas/", {"zone": value})
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, "no es válido")
                self.assertEqual(response.context["page"].paginator.count, 0)

    def test_invalid_initial_form_reference_is_reported(self):
        response = self.client.get("/gestion/contratos/nuevo/", {"space": "9" * 5000})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "El registro indicado en el enlace no es válido")

    def test_blank_map_search_does_not_return_people(self):
        response = self.client.get("/mapa/datos/", {"person": "   "})
        self.assertEqual(response.json()["people"], [])
        self.assertFalse(response.json()["people_truncated"])

    def test_full_name_search_matches_first_and_last_name(self):
        response = self.client.get("/gestion/personas/", {"q": " María   Prueba "})
        self.assertEqual(response.context["page"].paginator.count, 2)
        response = self.client.get("/mapa/datos/", {"person": "María Prueba"})
        self.assertEqual(len(response.json()["people"]), 2)

    def add_homonyms(self):
        Person.objects.bulk_create(
            [
                Person(first_name="María", last_name="Prueba", death_date=self.today)
                for _ in range(19)
            ]
        )

    def test_map_reports_truncated_homonyms(self):
        self.add_homonyms()
        result = self.client.get("/mapa/datos/", {"person": "María"}).json()
        self.assertEqual(len(result["people"]), 20)
        self.assertTrue(result["people_truncated"])

    def test_map_queries_do_not_grow_for_each_person(self):
        self.add_homonyms()
        request = RequestFactory().get("/mapa/datos/", {"person": "María"})
        request.user = self.admin
        with self.assertNumQueries(2):
            response = map_data(request)
            self.assertEqual(response.status_code, 200)

    def test_dashboard_aggregates_match_space_states(self):
        services.bury(self.admin, self.key(), self.burial_data())
        services.create_reservation(self.admin, self.key(), self.reservation_data())
        Space.objects.create(
            code="MAINT", block=self.block, row=2, number=1, condition="MAINTENANCE"
        )
        with self.assertNumQueries(1):
            counts = space_counts()
        for code in counts:
            self.assertEqual(counts[code], sum(s.status == code for s in spaces()))
        self.assertEqual(counts["OCCUPIED"], 1)
        self.assertEqual(counts["RESERVED"], 1)
        self.assertEqual(counts["MAINTENANCE"], 1)

    def test_history_search_filters_person_and_uses_spanish_labels(self):
        services.bury(self.admin, self.key(), self.burial_data())
        self.other_person.first_name = "Ana"
        self.other_person.save()
        Event.objects.create(
            space=self.space,
            person=self.other_person,
            kind="SPACE_UPDATED",
            detail="Evento de Ana",
            actor=self.admin,
        )
        response = self.client.get(
            f"/sepultura/{self.space.pk}/", {"person": "María Prueba"}
        )
        self.assertContains(response, "<h3>Inhumación</h3>", html=True)
        self.assertNotContains(response, "Evento de Ana")
        self.assertEqual(response.context["page"].paginator.count, 1)

    def test_oversized_search_has_a_clear_validation_error(self):
        self.assertEqual(
            self.client.get("/mapa/datos/", {"q": "x" * 201}).status_code, 400
        )
        response = self.client.get("/gestion/personas/", {"q": "x" * 201})
        self.assertContains(response, "hasta 200 caracteres")
        self.assertEqual(response.context["page"].paginator.count, 0)

    def test_contract_totals_and_rows_use_one_ledger_snapshot(self):
        from decimal import Decimal
        from cemetery.views import contract_detail

        services.record_payment(self.admin, self.key(), self.payment_data())
        request = RequestFactory().get(f"/contrato/{self.contract.pk}/")
        request.user = self.admin
        with self.assertNumQueries(2):
            response = contract_detail(request, self.contract.pk)
            self.assertEqual(response.status_code, 200)
        response = self.client.get(f"/contrato/{self.contract.pk}/")
        self.assertEqual(response.context["paid"], Decimal("300.00"))
        self.assertEqual(response.context["balance"], Decimal("700.00"))
        self.assertEqual(len(response.context["payments"]), 1)
