import logging

from drf_spectacular.utils import extend_schema
from pydantic import BaseModel
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.viewsets import GenericViewSet

from care.emr.models import Device
from gateway_device.client import GatewayClient
from lab_analyzer_device.hl7.devices.registry import registry
from lab_analyzer_device.models import MessageStatus
from lab_analyzer_device.services import build_order

logger = logging.getLogger(__name__)


class OrderedTestSpec(BaseModel):
    code: str
    display: str
    system: str = "http://loinc.org"


class SendOrderRequest(BaseModel):
    patient_id: str
    encounter_external_id: str | None = None
    specimen_external_id: str | None = None
    service_request_external_id: str | None = None
    placer_order_number: str
    sample_id: str | None = None
    tests: list[OrderedTestSpec]


class LabAnalyzerActionsViewSet(GenericViewSet):
    """
    User-authenticated endpoints for outbound lab analyzer actions.

    These are called by clinicians via the frontend (not by the gateway).
    """

    queryset = Device.objects.filter(care_type="lab-analyzer")
    lookup_field = "external_id"

    def get_gateway_client(self, device):
        gateway_external_id = device.metadata.get("gateway")
        if not gateway_external_id:
            raise ValidationError({"gateway": "Not configured"})
        try:
            gateway_device = Device.objects.get(
                external_id=gateway_external_id, care_type="gateway"
            )
        except Device.DoesNotExist as e:
            raise ValidationError("Gateway device not found") from e
        return GatewayClient(gateway_device)

    @extend_schema(request=SendOrderRequest)
    @action(detail=True, methods=["post"])
    def send_order(self, request, *args, **kwargs):
        """Send an ORM order to a lab analyzer via the gateway."""
        device = self.get_object()

        # Reject orders to unidirectional (results-only) devices
        device_type = device.metadata.get("type", "generic")
        profile = registry.get_profile(device_type)
        if profile.communication_mode == "unidirectional":
            raise ValidationError(
                {"device": "This device is unidirectional (results-only) and does not accept orders."}
            )

        data = SendOrderRequest(**request.data)

        if data.sample_id is not None:
            try:
                int(data.sample_id)
            except (TypeError, ValueError):
                raise ValidationError({"sample_id": "Must be an integer value"})

        try:
            result = build_order(
                device=device,
                patient_id=data.patient_id,
                placer_order_number=data.placer_order_number,
                tests=[t.model_dump() for t in data.tests],
                encounter_external_id=data.encounter_external_id,
                specimen_external_id=data.specimen_external_id,
                service_request_external_id=data.service_request_external_id,
                sample_id=data.sample_id,
            )
        except ValueError as e:
            raise ValidationError({"tests": str(e)}) from e

        # Dispatch to gateway. Serial-attached analyzers have no IP; the
        # gateway tracks their always-open link by the device id, so we send
        # that as the address and ride the shared link for ordering.
        transport = device.metadata.get("transport", "ethernet")
        if transport == "serial":
            device_ip = str(device.external_id)
            orm_mode = "shared"
            port = device.metadata.get("oru_port", 2575)
        else:
            device_ip = device.metadata.get("endpoint_address")
            orm_mode = device.metadata.get("orm_mode", "shared")
            port = device.metadata.get("orm_port") or device.metadata.get("oru_port", 2575)

        client = self.get_gateway_client(device)
        try:
            gateway_response = client.post(
                "/send-order/",
                data={
                    "device_ip": device_ip,
                    "port": port,
                    "raw_message": result.raw_message,
                    "orm_mode": orm_mode,
                },
            )
            result.lab_message.status = MessageStatus.ACKNOWLEDGED
            result.lab_message.save(update_fields=["status"])
            return Response({
                "message": "ok",
                "lab_message_id": str(result.lab_message.external_id),
                "sample_id": result.sample_id,
                "gateway_response": gateway_response,
            })
        except Exception as e:
            logger.exception("Failed to send ORM to gateway")
            result.lab_message.status = MessageStatus.ERROR
            result.lab_message.error_details = str(e)
            result.lab_message.save(update_fields=["status", "error_details"])
            return Response({"error": f"Failed to send order: {e}"}, status=502)
