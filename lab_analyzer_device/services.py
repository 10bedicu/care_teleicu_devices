"""Business logic for the lab analyzer device plugin."""

import logging
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone

from care.emr.models import (
    ActivityDefinition,
    DiagnosticReport,
    Encounter,
    Observation,
    Patient,
    ServiceRequest,
    Specimen,
)
from care.emr.models.observation_definition import ObservationDefinition
from care.emr.resources.observation_definition.observation import convert_od_to_observation
from care.emr.utils.compute_observation_interpretation import compute_observation_interpretation
from lab_analyzer_device.hl7.builder import ORMData, OrderedTest, OrderingPhysician, build_orm_message
from lab_analyzer_device.hl7.devices.registry import registry
from lab_analyzer_device.hl7.extractor import ORUData
from lab_analyzer_device.models import LabMessage, MessageStatus, MessageType

logger = logging.getLogger(__name__)


@dataclass
class PatientContext:
    patient: object | None = None
    encounter: object | None = None
    specimen: object | None = None
    service_request: object | None = None


def resolve_patient_context(oru_data, device) -> PatientContext:
    """
    Resolve patient/encounter/specimen context from an ORU result.

    Priority 1: Match via specimen accession_identifier (OBR-3 = sample number)
    Priority 2: Fall back to ORM correlation (placer/filler order number)
    """
    ctx = PatientContext()

    sample_id = oru_data.filler_order_number or oru_data.specimen_id
    if sample_id:
        specimen = (
            Specimen.objects.select_related("patient", "encounter", "service_request")
            .filter(accession_identifier=sample_id)
            .first()
        )
        if not specimen and sample_id.isdigit():
            specimen = (
                Specimen.objects.select_related("patient", "encounter", "service_request")
                .filter(id=int(sample_id))
                .first()
            )
        if specimen:
            ctx.specimen = specimen
            ctx.patient = specimen.patient
            ctx.encounter = specimen.encounter
            ctx.service_request = specimen.service_request

    # Fall back to ORM correlation via placer/filler order number
    if not ctx.patient and (oru_data.placer_order_number or oru_data.filler_order_number):
        orm_lookup = LabMessage.objects.filter(
            device=device, message_type=MessageType.ORM
        )
        if oru_data.placer_order_number:
            orm_lookup = orm_lookup.filter(
                parsed_data__placer_order_number=oru_data.placer_order_number
            )
        elif oru_data.filler_order_number:
            orm_lookup = orm_lookup.filter(
                parsed_data__filler_order_number=oru_data.filler_order_number
            )

        orm_message = orm_lookup.order_by("-created_date").first()
        if orm_message:
            ctx.patient = orm_message.patient
            ctx.encounter = orm_message.encounter
            ctx.specimen = ctx.specimen or orm_message.specimen
            if orm_message.specimen and orm_message.specimen.service_request:
                ctx.service_request = ctx.service_request or orm_message.specimen.service_request

    return ctx


def _resolve_observation_definition(service_request):
    """
    Resolve ObservationDefinition for a ServiceRequest.

    Priority 1: ServiceRequest -> ActivityDefinition -> observation_result_requirements
    Priority 2: Match OD by code in the same facility (fallback for missing activity_definition link)
    """
    # Priority 1: Follow the activity_definition chain
    if service_request.activity_definition_id:
        activity_def = ActivityDefinition.objects.filter(
            id=service_request.activity_definition_id
        ).first()
        if activity_def and activity_def.observation_result_requirements:
            od = ObservationDefinition.objects.filter(
                id__in=activity_def.observation_result_requirements
            ).first()
            if od:
                return od

    # Priority 2: Match OD by code in the same facility
    if service_request.code and isinstance(service_request.code, dict):
        sr_code = service_request.code.get("code")
        if sr_code:
            od = ObservationDefinition.objects.filter(
                facility=service_request.facility,
                code__code=sr_code,
                status="active",
            ).first()
            if od:
                return od
            # Also check global ODs (facility=None)
            od = ObservationDefinition.objects.filter(
                facility__isnull=True,
                code__code=sr_code,
                status="active",
            ).first()
            if od:
                return od

    return None


def _build_components(oru_data, observation_definition, device_type=None, protocol=None):
    """Build observation component list from OBX results, matching against OD components."""
    od_components = {}
    if observation_definition and observation_definition.component:
        for comp_def in observation_definition.component:
            code = comp_def.get("code", {}).get("code", "")
            if code:
                od_components[code] = comp_def

    # Get device profile for re-resolving unmapped codes
    profile = None
    if device_type:
        if protocol == "astm":
            from lab_analyzer_device.astm.devices.registry import registry as astm_registry
            profile = astm_registry.get_profile(device_type)
        else:
            from lab_analyzer_device.hl7.devices.registry import registry
            profile = registry.get_profile(device_type)

    components = []
    for obs_data in oru_data.observations:
        code = obs_data.code
        system = obs_data.system
        display = obs_data.display

        # Re-resolve unmapped codes through the device profile
        if system == "local" and profile and profile.code_mappings:
            mapping = profile.code_mappings.get(code)
            if mapping:
                system = mapping.system
                code = mapping.loinc_code
                display = mapping.display

        comp_def = od_components.get(code)
        if comp_def:
            component_code = comp_def.get("code", {})
        else:
            component_code = {
                "code": code,
                "system": system,
                "display": display,
            }

        component = {
            "code": component_code,
            "value": {"value": obs_data.value},
        }

        if obs_data.units:
            component["value"]["unit"] = {
                "code": obs_data.units,
                "system": "http://unitsofmeasure.org",
                "display": obs_data.units,
            }
        elif comp_def:
            permitted_unit = comp_def.get("permitted_unit")
            if permitted_unit:
                component["value"]["unit"] = permitted_unit

        components.append(component)

    return components


def create_diagnostic_report(oru_data, patient, encounter, service_request, user, device_type=None, protocol=None):
    """
    Create or update a DiagnosticReport from parsed ORU data.

    - If a completed (final) report already exists for the service_request, skip.
    - If a preliminary (draft) report exists, fill in the observation values.
    - Otherwise, create a new preliminary report with observation components.

    Returns the DiagnosticReport, or None if skipped.
    """
    if not service_request:
        logger.warning("No ServiceRequest found for lab result, skipping DiagnosticReport creation")
        return None

    existing_report = (
        DiagnosticReport.objects.filter(service_request=service_request)
        .order_by("-created_date")
        .first()
    )

    if existing_report and existing_report.status in ("final", "completed"):
        logger.info(
            "DiagnosticReport already completed for ServiceRequest %s, skipping",
            service_request.id,
        )
        return existing_report

    observation_definition = _resolve_observation_definition(service_request)

    if observation_definition:
        report_code = observation_definition.code
    elif service_request.code and isinstance(service_request.code, dict):
        report_code = service_request.code
    else:
        report_code = None

    components = _build_components(oru_data, observation_definition, device_type, protocol)

    if existing_report and existing_report.status == "preliminary":
        report = existing_report
        observation_obj = Observation.objects.filter(diagnostic_report=report).first()

        if observation_obj:
            observation_obj.component = components
            observation_obj.effective_datetime = datetime.now(timezone.utc)
            observation_obj.updated_by = user

            if observation_definition:
                observation_obj.observation_definition = observation_definition
                try:
                    compute_observation_interpretation(observation_obj, {})
                except Exception as e:
                    logger.warning("Failed to compute interpretation: %s", e)

            observation_obj.save()
            logger.info("Updated existing observation on draft report %s", report.id)
            return report
        # If no observation exists on the draft report, fall through to create one
    else:
        # Create new preliminary report
        report = DiagnosticReport.objects.create(
            status="preliminary",
            patient=patient,
            encounter=encounter,
            service_request=service_request,
            facility=encounter.facility,
            code=report_code,
            category={"code": "LAB", "system": "http://terminology.hl7.org/CodeSystem/v2-0074", "display": "Laboratory"},
        )

    # Create observation for the report
    if observation_definition:
        observation_obj = convert_od_to_observation(observation_definition, encounter)
    else:
        observation_obj = Observation(
            status="final",
            encounter=encounter,
            category="laboratory",
            main_code=report_code or {},
        )

    observation_obj.value_type = "quantity"
    observation_obj.value = {"value": ""}
    observation_obj.component = components
    observation_obj.effective_datetime = datetime.now(timezone.utc)
    observation_obj.note = ""
    observation_obj.patient = patient
    observation_obj.encounter = encounter
    observation_obj.subject_type = "encounter"
    observation_obj.subject_id = encounter.external_id
    observation_obj.diagnostic_report = report
    observation_obj.observation_definition = observation_definition
    observation_obj.created_by = user
    observation_obj.updated_by = user

    if observation_definition:
        try:
            compute_observation_interpretation(observation_obj, {})
        except Exception as e:
            logger.warning("Failed to compute interpretation: %s", e)

    observation_obj.save()

    return report


def lookup_pending_orders(sample_ids: list[str], device=None) -> tuple[list[ORUData], list[str]]:
    """
    Look up pending orders for the given sample IDs.

    Returns (orders, not_found_ids).
    """
    orders = []
    not_found = []

    panel_mappings: dict[str, str | list[str]] = {}
    if device:
        device_type = device.metadata.get("type", "generic")
        profile = registry.get_profile(device_type)
        panel_mappings = profile.get_effective_panel_mappings(device.metadata)

    for sample_id in sample_ids:
        specimen = (
            Specimen.objects.select_related("patient", "encounter", "service_request")
            .filter(accession_identifier=sample_id)
            .first()
        )

        if not specimen or not specimen.service_request:
            not_found.append(sample_id)
            continue

        patient = specimen.patient
        service_request = specimen.service_request

        patient_name = patient.name if patient else ""
        date_of_birth = ""
        if patient and patient.date_of_birth:
            date_of_birth = patient.date_of_birth.strftime("%Y%m%d%H%M%S")
        elif patient and patient.year_of_birth:
            date_of_birth = f"{patient.year_of_birth}0101000000"

        # HL7 gender codes per HL7 v2.x table 0001 / ADX-CHEM-200 spec:
        # M = Male, F = Female, O = Other, U = Unknown.
        # care GenderChoices: male, female, non_binary, transgender.
        gender = "U"
        if patient and patient.gender:
            gender_map = {
                "male": "M",
                "female": "F",
                "non_binary": "O",
                "transgender": "O",
                "other": "O",
            }
            gender = gender_map.get(patient.gender, "O")

        # Extract sample type display name
        sample_type = ""
        if specimen.specimen_type and isinstance(specimen.specimen_type, dict):
            sample_type = specimen.specimen_type.get("display", "")

        order = ORUData(
            sample_id=sample_id,
            patient_id=str(patient.id) if patient else "",
            patient_name=patient_name,
            date_of_birth=date_of_birth,
            gender=gender,
            sample_type=sample_type,
            department="",
            bed="",
            patient_class="",
            collect_time="",
            tests=[],
        )

        if service_request.code:
            code_data = service_request.code
            if isinstance(code_data, dict):
                loinc_code = code_data.get("code", "")
                device_code = panel_mappings.get(loinc_code, loinc_code)
                if isinstance(device_code, list):
                    # Panel expands to individual test IDs
                    for test_id in device_code:
                        order.tests.append(OrderedTest(code=test_id))
                else:
                    order.tests.append(OrderedTest(
                        code=device_code,
                        display=code_data.get("display", ""),
                        system=code_data.get("system", ""),
                    ))

        if specimen.collection and isinstance(specimen.collection, dict):
            collected_time = specimen.collection.get("collected_date_time")
            if collected_time:
                order.collect_time = collected_time

        orders.append(order)

    return orders, not_found


@dataclass
class OrderResult:
    lab_message: LabMessage
    raw_message: str
    sample_id: str | None


def build_order(
    device,
    patient_id: str,
    placer_order_number: str,
    tests: list[dict],
    encounter_external_id: str | None = None,
    specimen_external_id: str | None = None,
    service_request_external_id: str | None = None,
    sample_id: str | None = None,
) -> OrderResult:
    """
    Resolve context, build an ORM HL7 message, and persist it.

    Returns an OrderResult with the LabMessage and raw HL7 string.
    """
    patient = None
    encounter = None
    specimen = None

    if encounter_external_id:
        encounter = Encounter.objects.filter(
            external_id=encounter_external_id
        ).first()
        if encounter:
            patient = encounter.patient
    if not patient:
        patient = Patient.objects.filter(external_id=patient_id).first()
    if specimen_external_id:
        specimen = Specimen.objects.filter(
            external_id=specimen_external_id
        ).first()

    ordering_physician = None
    if service_request_external_id:
        service_request = ServiceRequest.objects.select_related("requester").filter(
            external_id=service_request_external_id
        ).first()
        if service_request and service_request.requester:
            user = service_request.requester
            ordering_physician = OrderingPhysician(
                id=str(user.id),
                family_name=user.last_name or "",
                given_name=user.first_name or "",
            )
        # Fallback: find specimen via service request if not already resolved
        if not specimen and service_request:
            specimen = Specimen.objects.filter(
                service_request=service_request,
                status__in=["available", "draft"],
            ).first()

    # Build HL7 ORM
    patient_name = patient.name if patient else ""
    date_of_birth = None
    if patient and patient.date_of_birth:
        date_of_birth = patient.date_of_birth.strftime("%Y%m%d")
    elif patient and patient.year_of_birth:
        date_of_birth = f"{patient.year_of_birth}0101"

    # HL7 v2.x administrative gender code (table 0001): M, F, O, U.
    gender = "U"
    if patient and patient.gender:
        gender_map = {
            "male": "M",
            "female": "F",
            "non_binary": "O",
            "transgender": "O",
            "other": "O",
        }
        gender = gender_map.get(patient.gender, "O")

    filler_order_number = sample_id
    if not filler_order_number and specimen:
        filler_order_number = specimen.accession_identifier

    if not filler_order_number:
        raise ValueError("sample_id is required: no accession_identifier available on specimen")
    try:
        int(filler_order_number)
    except (TypeError, ValueError):
        raise ValueError(
            f"sample_id must be an integer (got '{filler_order_number}'). "
            "Ensure the specimen accession_identifier is a numeric value."
        )

    device_type = device.metadata.get("type", "generic")
    ordered_tests = [OrderedTest(**t) for t in tests]

    order_data = ORMData(
        patient_id=str(patient.id) if patient else patient_id,
        placer_order_number=placer_order_number,
        filler_order_number=filler_order_number,
        patient_name=patient_name,
        date_of_birth=date_of_birth,
        gender=gender,
        ordering_physician=ordering_physician,
        tests=ordered_tests,
        specimen_id=filler_order_number,
    )
    orm_message = build_orm_message(order_data, device_type=device_type, device_metadata=device.metadata)
    raw_message = str(orm_message)

    try:
        control_id = str(orm_message.segment("MSH")(10))
    except (IndexError, KeyError):
        control_id = str(uuid.uuid4())

    lab_message = LabMessage.objects.create(
        device=device,
        patient=patient,
        encounter=encounter,
        specimen=specimen,
        message_type=MessageType.ORM,
        message_control_id=control_id,
        raw_message=raw_message,
        parsed_data=order_data.model_dump(mode="json"),
        status=MessageStatus.SENT,
    )

    return OrderResult(lab_message=lab_message, raw_message=raw_message, sample_id=filler_order_number)
