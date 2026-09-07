from lab_analyzer_device.models.message import Protocol
import logging
import uuid

import hl7
from drf_spectacular.utils import extend_schema
from pydantic import BaseModel, RootModel
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.viewsets import GenericViewSet

from care.emr.models import ActivityDefinition, Device
from care.emr.models.observation_definition import ObservationDefinition
from care.utils.pagination.care_pagination import CareLimitOffsetPagination
from lab_analyzer_device.astm import codec as astm_codec
from lab_analyzer_device.astm.devices.registry import registry as astm_registry
from lab_analyzer_device.astm.extractor import extract_astm_data
from lab_analyzer_device.authentication import LabAnalyzerAuthentication
from lab_analyzer_device.authorization import (
    get_gateway_linked_analyzers,
    is_context_in_device_facility,
)
from lab_analyzer_device.hl7.devices.registry import registry
from lab_analyzer_device.hl7.extractor import extract_oru_data
from lab_analyzer_device.models import LabMessage, MessageStatus, MessageType
from lab_analyzer_device.services import (
    PatientContext,
    create_diagnostic_report,
    lookup_pending_orders,
    resolve_patient_context,
)
from lab_analyzer_device.spec import (
    GatewayActivityDefinitionReadSpec,
    GatewayObservationDefinitionReadSpec,
    serialize_gateway_activity_definition,
    serialize_gateway_observation_definition,
)

logger = logging.getLogger(__name__)


class ReceiveResultRequest(BaseModel):
    raw_message: str
    sender_ip: str
    sender_device_id: str | None = None


class PendingOrdersRequest(BaseModel):
    sender_ip: str
    sample_ids: list[str]
    message_control_id: str | None = None
    raw_message: str | None = None
    sender_device_id: str | None = None


class DeviceConfigSpec(BaseModel):
    id: str
    registered_name: str | None = None
    transport: str = "ethernet"
    protocol: str = "hl7"
    endpoint_address: str | None = None
    oru_port: int = 2575
    orm_port: int | None = None
    orm_mode: str = "shared"
    hl7_connection_mode: str = "inbound"
    astm_connection_mode: str = "outbound"
    type: str = "generic"
    # Serial (RS232) line settings — only used when transport="serial"
    serial_port: str | None = None
    baud_rate: int | None = None
    data_bits: int | None = None
    parity: str | None = None
    stop_bits: float | None = None
    flow_control: str | None = None


class DeviceConfigListResponse(RootModel[list[DeviceConfigSpec]]):
    pass


class GatewayActivityDefinitionListResponse(
    RootModel[list[GatewayActivityDefinitionReadSpec]]
):
    pass


class GatewayObservationDefinitionListResponse(
    RootModel[list[GatewayObservationDefinitionReadSpec]]
):
    pass


class LabAnalyzerCommunicationViewSet(GenericViewSet):
    """
    Gateway-authenticated endpoints for inbound lab analyzer communication.

    These endpoints are called by the MLLP gateway (not by end users).
    """

    queryset = Device.objects.filter(care_type="lab-analyzer")
    lookup_field = "external_id"
    authentication_classes = (LabAnalyzerAuthentication,)
    pagination_class = CareLimitOffsetPagination

    def get_queryset(self):
        return get_gateway_linked_analyzers(self.request.gateway)

    def _paginate(self, queryset, serializer):
        page = self.paginate_queryset(queryset)
        if page is not None:
            return self.get_paginated_response([serializer(obj) for obj in page])
        return Response([serializer(obj) for obj in queryset])

    def _activity_definition_queryset(self, request):
        params = request.query_params
        qs = ActivityDefinition.objects.filter(
            facility_id=request.gateway.facility_id,
            classification=params.get("classification", "laboratory"),
            status=params.get("status", "active"),
        )
        latest = params.get("latest", "true").lower()
        if latest in ("1", "true", "yes"):
            qs = qs.filter(latest=True)
        elif latest in ("0", "false", "no"):
            qs = qs.filter(latest=False)

        title = params.get("title")
        if title:
            qs = qs.filter(title__icontains=title)
        kind = params.get("kind")
        if kind:
            qs = qs.filter(kind__iexact=kind)
        code = params.get("code")
        if code:
            qs = qs.filter(code__code=code)
        return qs.order_by("title")

    def _observation_definition_queryset(self, request):
        params = request.query_params
        qs = ObservationDefinition.objects.filter(
            facility_id=request.gateway.facility_id,
            category=params.get("category", "laboratory"),
            status=params.get("status", "active"),
        )
        title = params.get("title")
        if title:
            qs = qs.filter(title__icontains=title)
        code = params.get("code")
        if code:
            qs = qs.filter(code__code=code)
        return qs.order_by("title")

    @extend_schema(
        description="List all lab analyzer devices configured for this gateway.",
        responses={200: DeviceConfigListResponse},
    )
    def list(self, request, *args, **kwargs):
        """Return configured devices for the authenticated gateway."""
        queryset = self.get_queryset()
        devices = []
        for d in queryset:
            device_type = d.metadata.get("type", "generic")
            protocol = d.metadata.get("protocol", "hl7")
            profile = (
                astm_registry.get_profile(device_type)
                if protocol == "astm"
                else registry.get_profile(device_type)
            )
            transport = d.metadata.get("transport", "ethernet")
            serial_fields = (
                {
                    "serial_port": d.metadata.get("serial_port"),
                    "baud_rate": d.metadata.get("baud_rate") or 9600,
                    "data_bits": d.metadata.get("data_bits") or 8,
                    "parity": d.metadata.get("parity") or "N",
                    "stop_bits": d.metadata.get("stop_bits")
                    if d.metadata.get("stop_bits") is not None
                    else 1,
                    "flow_control": d.metadata.get("flow_control") or "none",
                }
                if transport == "serial"
                else {
                    "serial_port": None,
                    "baud_rate": None,
                    "data_bits": None,
                    "parity": None,
                    "stop_bits": None,
                    "flow_control": None,
                }
            )
            devices.append(
                DeviceConfigSpec(
                    id=str(d.external_id),
                    registered_name=d.registered_name,
                    transport=transport,
                    protocol=protocol,
                    endpoint_address=d.metadata.get("endpoint_address"),
                    oru_port=d.metadata.get("oru_port", profile.default_oru_port),
                    orm_port=d.metadata.get("orm_port"),
                    orm_mode=d.metadata.get("orm_mode", "shared"),
                    hl7_connection_mode=d.metadata.get(
                        "hl7_connection_mode",
                        getattr(profile, "hl7_connection_mode", "inbound"),
                    ),
                    astm_connection_mode=d.metadata.get(
                        "astm_connection_mode",
                        getattr(profile, "astm_connection_mode", "outbound"),
                    ),
                    type=device_type,
                    **serial_fields,
                ).model_dump(mode="json")
            )
        return Response(devices)

    @extend_schema(
        description=(
            "List Activity Definitions for the gateway's facility. "
            "Facility is resolved from X-Gateway-Id. Defaults to laboratory / active. "
            "Supports limit/offset pagination and filters."
        ),
        responses={200: GatewayActivityDefinitionListResponse},
    )
    @action(detail=False, methods=["get"])
    def activity_definitions(self, request, *args, **kwargs):
        """Return facility Activity Definitions for the authenticated gateway."""
        queryset = self._activity_definition_queryset(request)

        def serialize_page(page):
            od_ids: set[int] = set()
            for ad in page:
                od_ids.update(ad.observation_result_requirements or [])
            observation_definitions_by_id = {
                od.id: od
                for od in ObservationDefinition.objects.filter(id__in=od_ids)
            }
            return [
                serialize_gateway_activity_definition(
                    ad, observation_definitions_by_id
                )
                for ad in page
            ]

        page = self.paginate_queryset(queryset)
        if page is not None:
            return self.get_paginated_response(serialize_page(page))
        return Response(serialize_page(list(queryset)))

    @extend_schema(
        description=(
            "List Observation Definitions for the gateway's facility. "
            "Facility is resolved from X-Gateway-Id. Defaults to laboratory / active. "
            "Supports limit/offset pagination and filters."
        ),
        responses={200: GatewayObservationDefinitionListResponse},
    )
    @action(detail=False, methods=["get"])
    def observation_definitions(self, request, *args, **kwargs):
        """Return facility Observation Definitions for the authenticated gateway."""
        queryset = self._observation_definition_queryset(request)
        return self._paginate(queryset, serialize_gateway_observation_definition)

    def resolve_device(self, sender_ip, sender_device_id=None):
        """Resolve a lab analyzer device within this gateway.

        Serial devices have no IP, so the gateway sends ``sender_device_id``
        (the device's external id); it is matched first, falling back to the
        ``endpoint_address`` IP for Ethernet devices.
        """
        if sender_device_id:
            try:
                uuid.UUID(str(sender_device_id))
            except (ValueError, TypeError, AttributeError):
                # Older gateway retries mistakenly sent the peer IP here.
                logger.warning(
                    "Ignoring non-UUID sender_device_id=%s; falling back to sender_ip=%s",
                    sender_device_id,
                    sender_ip,
                )
            else:
                device = self.get_queryset().filter(external_id=sender_device_id).first()
                if device:
                    return device
        device = self.get_queryset().filter(
            metadata__endpoint_address=sender_ip
        ).first()
        if not device:
            logger.warning(
                "No device found for sender_ip=%s sender_device_id=%s on gateway=%s",
                sender_ip, sender_device_id, self.request.gateway.external_id,
            )
        return device

    def resolve_device_by_ip(self, sender_ip):
        """Backwards-compatible alias for :meth:`resolve_device`."""
        return self.resolve_device(sender_ip)

    @extend_schema(request=ReceiveResultRequest)
    @action(detail=False, methods=["post"])
    def receive_result(self, request, *args, **kwargs):
        """Receive an HL7 or ASTM result forwarded by the gateway."""
        data = ReceiveResultRequest(**request.data)

        device = self.resolve_device(data.sender_ip, data.sender_device_id)
        if not device:
            return Response(
                {"error": f"No device registered for {data.sender_device_id or data.sender_ip}"},
                status=404,
            )

        device_type = device.metadata.get("type", "generic")
        protocol = device.metadata.get("protocol", "hl7")

        if protocol == "astm":
            return self._receive_astm_result(data, device, device_type, request)
        return self._receive_hl7_result(data, device, device_type, request)

    def _receive_astm_result(self, data, device, device_type, request):
        """Parse and process an ASTM result message."""
        protocol = device.metadata.get("protocol", "astm")
        records = astm_codec.split_lines(data.raw_message)
        if not records:
            LabMessage.objects.create(
                device=device,
                message_type=MessageType.ORU,
                message_control_id="PARSE_ERROR",
                raw_message=data.raw_message,
                status=MessageStatus.ERROR,
                error_details="Empty ASTM message",
            )
            return Response({"error": "Empty ASTM message"}, status=400)

        control_id = str(uuid.uuid4())
        oru_data = extract_astm_data(records, device_type, device.metadata)
        profile = astm_registry.get_profile(device_type)

        if profile.should_skip_result(oru_data):
            lab_message = LabMessage.objects.create(
                device=device,
                message_type=MessageType.ORU,
                protocol=Protocol.ASTM,
                message_control_id=control_id,
                raw_message=data.raw_message,
                parsed_data=oru_data.model_dump(mode="json"),
                status=MessageStatus.PROCESSED,
                error_details="Skipped: internal validation sample",
            )
            return Response(
                {
                    "message": "skipped",
                    "reason": "validation_sample",
                    "lab_message_id": str(lab_message.external_id),
                }
            )

        ctx = resolve_patient_context(oru_data, device)
        if not is_context_in_device_facility(ctx, device):
            logger.warning(
                "Resolved patient context outside device facility for gateway=%s device=%s",
                self.request.gateway.external_id,
                device.external_id,
            )
            ctx = PatientContext()

        lab_message = LabMessage.objects.create(
            device=device,
            patient=ctx.patient,
            encounter=ctx.encounter,
            specimen=ctx.specimen,
            message_type=MessageType.ORU,
            protocol=Protocol.ASTM,
            message_control_id=control_id,
            raw_message=data.raw_message,
            parsed_data=oru_data.model_dump(mode="json"),
            status=MessageStatus.RECEIVED,
        )

        if ctx.patient and ctx.encounter:
            try:
                diagnostic_report = create_diagnostic_report(
                    oru_data, ctx.patient, ctx.encounter,
                    ctx.service_request, request.user,
                    device_type=device_type,
                    protocol=protocol,
                    device=device,
                    lab_message=lab_message,
                )
                lab_message.status = MessageStatus.PROCESSED
                lab_message.diagnostic_report = diagnostic_report
                lab_message.save(update_fields=["status", "diagnostic_report"])
            except Exception as e:
                logger.exception("Failed to process ASTM results")
                lab_message.status = MessageStatus.ERROR
                lab_message.error_details = str(e)
                lab_message.save(update_fields=["status", "error_details"])

        return Response({"message": "ok", "lab_message_id": str(lab_message.external_id)})

    def _receive_hl7_result(self, data, device, device_type, request):
        """Parse and process an HL7 ORU result message."""
        protocol = device.metadata.get("protocol", "hl7")
        # Normalize line endings (gateway converts \r to \n)
        try:
            normalized = data.raw_message.replace("\r\n", "\r").replace("\n", "\r")
            message = hl7.parse(normalized)
        except Exception as e:
            logger.error("Failed to parse HL7 message: %s", e)
            LabMessage.objects.create(
                device=device,
                message_type=MessageType.ORU,
                protocol=Protocol.HL7,
                message_control_id="PARSE_ERROR",
                raw_message=data.raw_message,
                status=MessageStatus.ERROR,
                error_details=str(e),
            )
            return Response({"error": "Failed to parse HL7 message"}, status=400)

        try:
            control_id = str(message.segment("MSH")(10))
        except (IndexError, KeyError):
            control_id = str(uuid.uuid4())

        oru_data = extract_oru_data(message, device_type)

        # Ensure observation codes are resolved through device profile
        # (safety net in case extraction used a stale/generic profile)
        if device_type != "generic":
            profile = registry.get_profile(device_type)
            if profile.code_mappings:
                for obs in oru_data.observations:
                    if obs.system == "local":
                        mapping = profile.code_mappings.get(obs.code)
                        if mapping:
                            obs.code = mapping.loinc_code
                            obs.system = mapping.system
                            obs.display = obs.display or mapping.display

        ctx = resolve_patient_context(oru_data, device)
        if not is_context_in_device_facility(ctx, device):
            logger.warning(
                "Resolved patient context outside device facility for gateway=%s device=%s",
                self.request.gateway.external_id,
                device.external_id,
            )
            ctx = PatientContext()

        lab_message = LabMessage.objects.create(
            device=device,
            patient=ctx.patient,
            encounter=ctx.encounter,
            specimen=ctx.specimen,
            message_type=MessageType.ORU,
            protocol=Protocol.HL7,
            message_control_id=control_id,
            raw_message=data.raw_message,
            parsed_data=oru_data.model_dump(mode="json"),
            status=MessageStatus.RECEIVED,
        )

        if ctx.patient and ctx.encounter:
            try:
                diagnostic_report = create_diagnostic_report(
                    oru_data, ctx.patient, ctx.encounter,
                    ctx.service_request, request.user,
                    device_type=device_type,
                    protocol=protocol,
                    device=device,
                    lab_message=lab_message,
                )
                lab_message.status = MessageStatus.PROCESSED
                lab_message.diagnostic_report = diagnostic_report
                lab_message.save(update_fields=["status", "diagnostic_report"])
            except Exception as e:
                logger.exception("Failed to process ORU results")
                lab_message.status = MessageStatus.ERROR
                lab_message.error_details = str(e)
                lab_message.save(update_fields=["status", "error_details"])

        return Response({"message": "ok", "lab_message_id": str(lab_message.external_id)})

    @extend_schema(request=PendingOrdersRequest)
    @action(detail=False, methods=["post"])
    def pending_orders(self, request, *args, **kwargs):
        """Look up pending orders for sample IDs queried by the analyzer."""
        data = PendingOrdersRequest(**request.data)

        device = self.resolve_device(data.sender_ip, data.sender_device_id)
        if not device:
            return Response(
                {"error": f"No device registered for {data.sender_device_id or data.sender_ip}"},
                status=404,
            )

        # Only host_query devices should be querying for orders
        device_type = device.metadata.get("type", "generic")
        protocol = device.metadata.get("protocol", "hl7")
        profile = (
            astm_registry.get_profile(device_type)
            if protocol == "astm"
            else registry.get_profile(device_type)
        )
        if profile.communication_mode != "host_query":
            return Response(
                {"error": "This device does not support host query orders"}, status=400
            )

        orders, not_found = lookup_pending_orders(data.sample_ids, device=device)

        # Save the incoming QRY message with appropriate status
        qry_status = MessageStatus.RECEIVED if orders else MessageStatus.REJECTED
        if data.raw_message:
            LabMessage.objects.create(
                device=device,
                message_type=MessageType.QRY,
                message_control_id=data.message_control_id or "",
                raw_message=data.raw_message,
                status=qry_status,
            )

        # Build a device-specific worklist response if the profile supports it.
        raw_response = None
        if orders and (protocol == "astm" or data.message_control_id):
            raw_response = profile.build_worklist_response(
                orders, data.message_control_id, raw_query=data.raw_message
            )

        # Save the outbound response message (worklist sent to device)
        if raw_response:
            response_raw = raw_response if isinstance(raw_response, str) else "\n---\n".join(raw_response)
            LabMessage.objects.create(
                device=device,
                message_type=MessageType.DSP,
                message_control_id=data.message_control_id or "",
                raw_message=response_raw,
                parsed_data={"orders_count": len(orders), "sample_ids": data.sample_ids},
                status=MessageStatus.SENT,
            )

        response_payload = {
            "orders": [o.model_dump(mode="json") for o in orders],
            "device_type": device_type,
            "not_found": not_found,
        }
        # Keep protocol-specific keys so the gateway frames the response correctly.
        if protocol == "astm":
            response_payload["raw_astm_response"] = raw_response
        else:
            response_payload["raw_hl7_response"] = raw_response
        return Response(response_payload)
