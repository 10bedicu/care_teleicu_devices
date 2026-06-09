"""Unit tests for lab_analyzer_device.services module.

These tests mock the Django ORM and CARE backend dependencies so they can
run without a database or Django setup.
"""

import sys
import unittest
from datetime import date, datetime, timezone
from unittest.mock import MagicMock, Mock, patch

# ──────────────────────────────────────────────────────────────────────
# Pre-import mocking: services.py imports Django models and CARE modules
# at module level. We inject mocks for all missing top-level packages
# so the module can be loaded in a vanilla Python environment.
# ──────────────────────────────────────────────────────────────────────

_django_mock = MagicMock()
_care_mock = MagicMock()

# Django
for mod in [
    "django", "django.db", "django.db.models",
    "django.conf", "django.conf.settings",
]:
    sys.modules.setdefault(mod, _django_mock)

# care.emr hierarchy
for mod in [
    "care", "care.emr", "care.emr.models",
    "care.emr.models.observation_definition",
    "care.emr.resources",
    "care.emr.resources.observation_definition",
    "care.emr.resources.observation_definition.observation",
    "care.emr.utils",
    "care.emr.utils.compute_observation_interpretation",
]:
    sys.modules.setdefault(mod, _care_mock)

# lab_analyzer_device.models also imports Django models
_lab_models_mock = MagicMock()
sys.modules.setdefault("lab_analyzer_device.models", _lab_models_mock)
sys.modules.setdefault("lab_analyzer_device.models.device_activity_definition", _lab_models_mock)
sys.modules.setdefault("lab_analyzer_device.models.message", _lab_models_mock)

# Now we can import services
import lab_analyzer_device.services as services  # noqa: E402
from lab_analyzer_device.hl7.extractor import ObservationData, ORUData  # noqa: E402

# Wire up model classes that services.py references via `from ... import`
services.Specimen = MagicMock()
services.Patient = MagicMock()
services.Encounter = MagicMock()
services.ServiceRequest = MagicMock()
services.DiagnosticReport = MagicMock()
services.Observation = MagicMock()
services.ActivityDefinition = MagicMock()
services.ObservationDefinition = MagicMock()
services.LabMessage = MagicMock()
services.MessageType = MagicMock()
services.MessageStatus = MagicMock()
services.convert_od_to_observation = MagicMock()
services.compute_observation_interpretation = MagicMock()


class TestLookupPendingOrders(unittest.TestCase):
    """Tests for the lookup_pending_orders function."""

    @patch("lab_analyzer_device.services.Specimen")
    @patch("lab_analyzer_device.services.registry")
    def test_returns_orders_for_found_specimens(self, mock_registry, mock_specimen_model):
        from lab_analyzer_device.services import lookup_pending_orders

        # Setup mock patient
        patient = Mock()
        patient.name = "John Doe"
        patient.date_of_birth = date(1990, 1, 15)
        patient.year_of_birth = None
        patient.gender = "male"
        patient.id = 42

        # Setup mock service_request
        service_request = Mock()
        service_request.code = {"code": "58410-2", "display": "CBC", "system": "http://loinc.org"}

        # Setup mock specimen
        specimen = Mock()
        specimen.patient = patient
        specimen.service_request = service_request
        specimen.specimen_type = {"display": "Whole Blood"}
        specimen.collection = {"collected_date_time": "20250115120000"}

        # Wire up queryset
        qs = Mock()
        qs.select_related.return_value = qs
        qs.filter.return_value = qs
        qs.first.return_value = specimen
        mock_specimen_model.objects = qs

        # Setup device with profile
        device = Mock()
        device.metadata = {"type": "cellquant_bf_6900"}
        mock_profile = Mock()
        mock_profile.get_effective_panel_mappings.return_value = {"58410-2": "1001"}
        mock_registry.get_profile.return_value = mock_profile

        orders, not_found = lookup_pending_orders(["SAMPLE001"], device=device)

        self.assertEqual(len(orders), 1)
        self.assertEqual(len(not_found), 0)
        self.assertEqual(orders[0].sample_id, "SAMPLE001")
        self.assertEqual(orders[0].patient_name, "John Doe")
        self.assertEqual(orders[0].gender, "M")
        self.assertEqual(orders[0].sample_type, "Whole Blood")
        self.assertEqual(orders[0].collect_time, "20250115120000")
        # Panel mapping resolved
        self.assertEqual(orders[0].tests[0].code, "1001")

    @patch("lab_analyzer_device.services.Specimen")
    @patch("lab_analyzer_device.services.registry")
    def test_returns_not_found_for_missing_specimen(self, mock_registry, mock_specimen_model):
        from lab_analyzer_device.services import lookup_pending_orders

        qs = Mock()
        qs.select_related.return_value = qs
        qs.filter.return_value = qs
        qs.first.return_value = None
        mock_specimen_model.objects = qs

        device = Mock()
        device.metadata = {"type": "generic"}
        mock_profile = Mock()
        mock_profile.get_effective_panel_mappings.return_value = {}
        mock_registry.get_profile.return_value = mock_profile

        orders, not_found = lookup_pending_orders(["MISSING001"], device=device)

        self.assertEqual(len(orders), 0)
        self.assertEqual(not_found, ["MISSING001"])

    @patch("lab_analyzer_device.services.Specimen")
    @patch("lab_analyzer_device.services.registry")
    def test_returns_not_found_when_no_service_request(self, mock_registry, mock_specimen_model):
        from lab_analyzer_device.services import lookup_pending_orders

        specimen = Mock()
        specimen.patient = Mock()
        specimen.service_request = None

        qs = Mock()
        qs.select_related.return_value = qs
        qs.filter.return_value = qs
        qs.first.return_value = specimen
        mock_specimen_model.objects = qs

        device = Mock()
        device.metadata = {"type": "generic"}
        mock_profile = Mock()
        mock_profile.get_effective_panel_mappings.return_value = {}
        mock_registry.get_profile.return_value = mock_profile

        orders, not_found = lookup_pending_orders(["SAMPLE002"], device=device)

        self.assertEqual(len(orders), 0)
        self.assertEqual(not_found, ["SAMPLE002"])

    @patch("lab_analyzer_device.services.Specimen")
    @patch("lab_analyzer_device.services.registry")
    def test_gender_mapping(self, mock_registry, mock_specimen_model):
        from lab_analyzer_device.services import lookup_pending_orders

        device = Mock()
        device.metadata = {"type": "generic"}
        mock_profile = Mock()
        mock_profile.get_effective_panel_mappings.return_value = {}
        mock_registry.get_profile.return_value = mock_profile

        gender_expected = [
            ("male", "M"),
            ("female", "F"),
            ("non_binary", "O"),
            ("transgender", "O"),
            (None, "U"),
        ]

        for gender, expected_gender in gender_expected:
            patient = Mock()
            patient.name = "Test"
            patient.date_of_birth = None
            patient.year_of_birth = 1990
            patient.gender = gender
            patient.id = 1

            service_request = Mock()
            service_request.code = None

            specimen = Mock()
            specimen.patient = patient
            specimen.service_request = service_request
            specimen.specimen_type = None
            specimen.collection = None

            qs = Mock()
            qs.select_related.return_value = qs
            qs.filter.return_value = qs
            qs.first.return_value = specimen
            mock_specimen_model.objects = qs

            orders, _ = lookup_pending_orders(["S1"], device=device)
            self.assertEqual(
                orders[0].gender, expected_gender,
                f"Gender '{gender}' should map to '{expected_gender}'"
            )

    @patch("lab_analyzer_device.services.Specimen")
    @patch("lab_analyzer_device.services.registry")
    def test_panel_mapping_list_expansion(self, mock_registry, mock_specimen_model):
        """When panel_mappings returns a list, each test ID becomes a separate entry."""
        from lab_analyzer_device.services import lookup_pending_orders

        patient = Mock()
        patient.name = "Test"
        patient.date_of_birth = None
        patient.year_of_birth = None
        patient.gender = None
        patient.id = 1

        service_request = Mock()
        service_request.code = {"code": "69738-3", "display": "CBC+DIFF", "system": "http://loinc.org"}

        specimen = Mock()
        specimen.patient = patient
        specimen.service_request = service_request
        specimen.specimen_type = None
        specimen.collection = None

        qs = Mock()
        qs.select_related.return_value = qs
        qs.filter.return_value = qs
        qs.first.return_value = specimen
        mock_specimen_model.objects = qs

        device = Mock()
        device.metadata = {"type": "test_device"}
        mock_profile = Mock()
        # Panel expands to multiple test IDs
        mock_profile.get_effective_panel_mappings.return_value = {"69738-3": ["7", "6", "3"]}
        mock_registry.get_profile.return_value = mock_profile

        orders, _ = lookup_pending_orders(["S1"], device=device)

        self.assertEqual(len(orders[0].tests), 3)
        self.assertEqual(orders[0].tests[0].code, "7")
        self.assertEqual(orders[0].tests[1].code, "6")
        self.assertEqual(orders[0].tests[2].code, "3")


class TestResolvePatientContext(unittest.TestCase):
    """Tests for the resolve_patient_context function."""

    @patch("lab_analyzer_device.services.Specimen")
    @patch("lab_analyzer_device.services.LabMessage")
    def test_resolves_via_specimen_accession_identifier(self, mock_lab_message, mock_specimen_model):
        from lab_analyzer_device.services import resolve_patient_context

        patient = Mock()
        encounter = Mock()
        service_request = Mock()

        specimen = Mock()
        specimen.patient = patient
        specimen.encounter = encounter
        specimen.service_request = service_request

        qs = Mock()
        qs.select_related.return_value = qs
        qs.filter.return_value = qs
        qs.first.return_value = specimen
        mock_specimen_model.objects = qs

        oru_data = Mock()
        oru_data.filler_order_number = "12345"
        oru_data.specimen_id = None
        oru_data.placer_order_number = None

        device = Mock()
        ctx = resolve_patient_context(oru_data, device)

        self.assertEqual(ctx.patient, patient)
        self.assertEqual(ctx.encounter, encounter)
        self.assertEqual(ctx.specimen, specimen)
        self.assertEqual(ctx.service_request, service_request)

    @patch("lab_analyzer_device.services.Specimen")
    @patch("lab_analyzer_device.services.LabMessage")
    def test_falls_back_to_orm_correlation(self, mock_lab_message, mock_specimen_model):
        from lab_analyzer_device.services import resolve_patient_context

        # No specimen found
        qs = Mock()
        qs.select_related.return_value = qs
        qs.filter.return_value = qs
        qs.first.return_value = None
        mock_specimen_model.objects = qs

        # ORM correlation found
        patient = Mock()
        encounter = Mock()
        orm_specimen = Mock()
        orm_specimen.service_request = Mock()

        orm_message = Mock()
        orm_message.patient = patient
        orm_message.encounter = encounter
        orm_message.specimen = orm_specimen

        orm_qs = Mock()
        orm_qs.filter.return_value = orm_qs
        orm_qs.order_by.return_value = orm_qs
        orm_qs.first.return_value = orm_message
        mock_lab_message.objects = orm_qs

        oru_data = Mock()
        oru_data.filler_order_number = None
        oru_data.specimen_id = None
        oru_data.placer_order_number = "PLAC001"

        device = Mock()
        ctx = resolve_patient_context(oru_data, device)

        self.assertEqual(ctx.patient, patient)
        self.assertEqual(ctx.encounter, encounter)

    @patch("lab_analyzer_device.services.Specimen")
    @patch("lab_analyzer_device.services.LabMessage")
    def test_returns_empty_context_when_nothing_found(self, mock_lab_message, mock_specimen_model):
        from lab_analyzer_device.services import resolve_patient_context

        qs = Mock()
        qs.select_related.return_value = qs
        qs.filter.return_value = qs
        qs.first.return_value = None
        mock_specimen_model.objects = qs

        oru_data = Mock()
        oru_data.filler_order_number = None
        oru_data.specimen_id = None
        oru_data.placer_order_number = None

        device = Mock()
        ctx = resolve_patient_context(oru_data, device)

        self.assertIsNone(ctx.patient)
        self.assertIsNone(ctx.encounter)
        self.assertIsNone(ctx.specimen)


class TestBuildComponents(unittest.TestCase):
    """Tests for the _build_components function."""

    @patch("lab_analyzer_device.services.registry")
    def test_builds_components_from_observations(self, mock_registry):
        from lab_analyzer_device.services import _build_components

        mock_registry.get_profile.return_value = Mock(code_mappings={})

        oru_data = Mock()
        oru_data.observations = [
            ObservationData(
                set_id=1,
                value_type="NM",
                code="6690-2",
                display="WBC",
                system="http://loinc.org",
                value="7.2",
                units="10^3/uL",
                reference_range="4-10",
                abnormal_flags="N",
                result_status="F",
            ),
            ObservationData(
                set_id=2,
                value_type="NM",
                code="789-8",
                display="RBC",
                system="http://loinc.org",
                value="4.5",
                units="10^6/uL",
                reference_range="4-6",
                abnormal_flags="N",
                result_status="F",
            ),
        ]

        components = _build_components(oru_data, observation_definition=None)

        self.assertEqual(len(components), 2)
        self.assertEqual(components[0]["code"]["code"], "6690-2")
        self.assertEqual(components[0]["value"]["value"], "7.2")
        self.assertEqual(components[0]["value"]["unit"]["code"], "10^3/uL")
        self.assertEqual(components[1]["code"]["code"], "789-8")
        self.assertEqual(components[1]["value"]["value"], "4.5")

    @patch("lab_analyzer_device.services.registry")
    def test_matches_observation_definition_components(self, mock_registry):
        from lab_analyzer_device.services import _build_components

        mock_registry.get_profile.return_value = Mock(code_mappings={})

        oru_data = Mock()
        oru_data.observations = [
            ObservationData(
                set_id=1,
                value_type="NM",
                code="6690-2",
                display="WBC",
                system="http://loinc.org",
                value="7.2",
                units="",
                reference_range="",
                abnormal_flags="",
                result_status="F",
            ),
        ]

        # OD has a component matching this code with a permitted_unit
        observation_definition = Mock()
        observation_definition.component = [
            {
                "code": {"code": "6690-2", "system": "http://loinc.org", "display": "WBC"},
                "permitted_unit": {"code": "10*3/uL", "system": "http://unitsofmeasure.org", "display": "10^3/uL"},
            }
        ]

        components = _build_components(oru_data, observation_definition)

        self.assertEqual(len(components), 1)
        # Should use OD code structure
        self.assertEqual(components[0]["code"]["system"], "http://loinc.org")
        # No units from OBX, should fall back to OD permitted_unit
        self.assertEqual(components[0]["value"]["unit"]["code"], "10*3/uL")

    @patch("lab_analyzer_device.services.registry")
    def test_re_resolves_local_codes_through_profile(self, mock_registry):
        from lab_analyzer_device.services import _build_components

        # Profile has a mapping for the local code
        mock_profile = Mock()
        mock_mapping = Mock()
        mock_mapping.system = "http://loinc.org"
        mock_mapping.loinc_code = "6690-2"
        mock_mapping.display = "WBC"
        mock_profile.code_mappings = {"WBC": mock_mapping}
        mock_registry.get_profile.return_value = mock_profile

        oru_data = Mock()
        oru_data.observations = [
            ObservationData(
                set_id=1,
                value_type="NM",
                code="WBC",
                display="",
                system="local",
                value="7.2",
                units="10^3/uL",
                reference_range="",
                abnormal_flags="",
                result_status="F",
            ),
        ]

        components = _build_components(oru_data, observation_definition=None, device_type="adx_heme_340")

        # Code should be re-resolved to LOINC
        self.assertEqual(components[0]["code"]["code"], "6690-2")
        self.assertEqual(components[0]["code"]["system"], "http://loinc.org")


class TestBuildOrder(unittest.TestCase):
    """Tests for the build_order function."""

    @patch("lab_analyzer_device.services.LabMessage")
    @patch("lab_analyzer_device.services.Specimen")
    @patch("lab_analyzer_device.services.ServiceRequest")
    @patch("lab_analyzer_device.services.Patient")
    @patch("lab_analyzer_device.services.Encounter")
    @patch("lab_analyzer_device.services.build_orm_message")
    def test_build_order_basic(
        self, mock_build_orm, mock_encounter, mock_patient,
        mock_service_request, mock_specimen_model, mock_lab_message
    ):
        from lab_analyzer_device.services import build_order

        import hl7

        # Mock patient
        patient = Mock()
        patient.name = "John Doe"
        patient.date_of_birth = date(1990, 1, 15)
        patient.year_of_birth = None
        patient.id = 42

        patient_qs = Mock()
        patient_qs.filter.return_value = patient_qs
        patient_qs.first.return_value = patient
        mock_patient.objects = patient_qs

        # Mock encounter
        encounter = Mock()
        encounter.patient = patient
        encounter_qs = Mock()
        encounter_qs.filter.return_value = encounter_qs
        encounter_qs.first.return_value = encounter
        mock_encounter.objects = encounter_qs

        # Mock specimen
        specimen = Mock()
        specimen.accession_identifier = "12345"
        specimen_qs = Mock()
        specimen_qs.filter.return_value = specimen_qs
        specimen_qs.first.return_value = specimen
        mock_specimen_model.objects = specimen_qs

        # Mock service_request (no requester)
        sr_qs = Mock()
        sr_qs.select_related.return_value = sr_qs
        sr_qs.filter.return_value = sr_qs
        sr_qs.first.return_value = None
        mock_service_request.objects = sr_qs

        # Mock build_orm_message to return a real HL7 message
        raw = "MSH|^~\\&|LIS||||20250101||ORM^O01|ORM20250101|P|2.3\rPID|1||42\rORC|NW|PLAC001|12345\rOBR|1|PLAC001|12345|CBC^CBC^http://loinc.org"
        mock_build_orm.return_value = hl7.parse(raw)

        # Mock LabMessage.objects.create
        lab_msg = Mock()
        mock_lab_message.objects.create.return_value = lab_msg

        device = Mock()
        device.metadata = {"type": "generic"}

        result = build_order(
            device=device,
            patient_id="ext-id-123",
            placer_order_number="PLAC001",
            tests=[{"code": "CBC", "display": "CBC", "system": "http://loinc.org"}],
            encounter_external_id="enc-ext-001",
            specimen_external_id="spec-ext-001",
            sample_id="12345",
        )

        self.assertEqual(result.sample_id, "12345")
        self.assertIn("ORM", result.raw_message)
        mock_lab_message.objects.create.assert_called_once()

    @patch("lab_analyzer_device.services.LabMessage")
    @patch("lab_analyzer_device.services.Specimen")
    @patch("lab_analyzer_device.services.ServiceRequest")
    @patch("lab_analyzer_device.services.Patient")
    @patch("lab_analyzer_device.services.Encounter")
    @patch("lab_analyzer_device.services.build_orm_message")
    def test_build_order_requires_numeric_sample_id(
        self, mock_build_orm, mock_encounter, mock_patient,
        mock_service_request, mock_specimen_model, mock_lab_message
    ):
        from lab_analyzer_device.services import build_order

        patient = Mock()
        patient.name = "Test"
        patient.date_of_birth = None
        patient.year_of_birth = None
        patient.id = 1

        patient_qs = Mock()
        patient_qs.filter.return_value = patient_qs
        patient_qs.first.return_value = patient
        mock_patient.objects = patient_qs

        encounter_qs = Mock()
        encounter_qs.filter.return_value = encounter_qs
        encounter_qs.first.return_value = None
        mock_encounter.objects = encounter_qs

        specimen = Mock()
        specimen.accession_identifier = "NOT_A_NUMBER"
        specimen_qs = Mock()
        specimen_qs.filter.return_value = specimen_qs
        specimen_qs.first.return_value = specimen
        mock_specimen_model.objects = specimen_qs

        sr_qs = Mock()
        sr_qs.select_related.return_value = sr_qs
        sr_qs.filter.return_value = sr_qs
        sr_qs.first.return_value = None
        mock_service_request.objects = sr_qs

        device = Mock()
        device.metadata = {"type": "generic"}

        with self.assertRaises(ValueError) as cm:
            build_order(
                device=device,
                patient_id="P1",
                placer_order_number="PLAC001",
                tests=[{"code": "CBC", "display": "CBC"}],
                specimen_external_id="spec-ext",
            )
        self.assertIn("must be an integer", str(cm.exception))

    @patch("lab_analyzer_device.services.LabMessage")
    @patch("lab_analyzer_device.services.Specimen")
    @patch("lab_analyzer_device.services.ServiceRequest")
    @patch("lab_analyzer_device.services.Patient")
    @patch("lab_analyzer_device.services.Encounter")
    def test_build_order_raises_when_no_sample_id(
        self, mock_encounter, mock_patient,
        mock_service_request, mock_specimen_model, mock_lab_message
    ):
        from lab_analyzer_device.services import build_order

        patient = Mock()
        patient.name = "Test"
        patient.date_of_birth = None
        patient.year_of_birth = None
        patient.id = 1

        patient_qs = Mock()
        patient_qs.filter.return_value = patient_qs
        patient_qs.first.return_value = patient
        mock_patient.objects = patient_qs

        encounter_qs = Mock()
        encounter_qs.filter.return_value = encounter_qs
        encounter_qs.first.return_value = None
        mock_encounter.objects = encounter_qs

        # No specimen found and no sample_id provided
        specimen_qs = Mock()
        specimen_qs.filter.return_value = specimen_qs
        specimen_qs.first.return_value = None
        mock_specimen_model.objects = specimen_qs

        sr_qs = Mock()
        sr_qs.select_related.return_value = sr_qs
        sr_qs.filter.return_value = sr_qs
        sr_qs.first.return_value = None
        mock_service_request.objects = sr_qs

        device = Mock()
        device.metadata = {"type": "generic"}

        with self.assertRaises(ValueError) as cm:
            build_order(
                device=device,
                patient_id="P1",
                placer_order_number="PLAC001",
                tests=[{"code": "CBC", "display": "CBC"}],
            )
        self.assertIn("sample_id is required", str(cm.exception))


class TestPatientContext(unittest.TestCase):
    """Tests for the PatientContext dataclass."""

    def test_defaults_to_none(self):
        from lab_analyzer_device.services import PatientContext

        ctx = PatientContext()
        self.assertIsNone(ctx.patient)
        self.assertIsNone(ctx.encounter)
        self.assertIsNone(ctx.specimen)
        self.assertIsNone(ctx.service_request)


if __name__ == "__main__":
    unittest.main()
