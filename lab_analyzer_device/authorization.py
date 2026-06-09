"""Authorization helpers for lab analyzer device endpoints."""

from care.emr.models import Device, Specimen
from care.security.authorization import AuthorizationController
from care.utils.shortcuts import get_object_or_404
from rest_framework.exceptions import PermissionDenied, ValidationError


def get_gateway_linked_analyzers(gateway):
    """Return lab-analyzer devices linked to this gateway within the same facility."""
    return Device.objects.filter(
        care_type="lab-analyzer",
        metadata__gateway=str(gateway.external_id),
        facility=gateway.facility,
    )


def get_lab_analyzer_device(external_id):
    return get_object_or_404(
        Device, external_id=external_id, care_type="lab-analyzer"
    )


def authorize_read_lab_analyzer(user, device):
    if not AuthorizationController.call("can_read_device", user, device):
        raise PermissionDenied("You do not have permission to access this device")


def authorize_manage_lab_analyzer(user, device):
    if not AuthorizationController.call("can_manage_device", user, device):
        raise PermissionDenied("You do not have permission to manage this device")


def assert_entity_in_device_facility(entity, device, label="resource"):
    if entity is None:
        return
    facility_id = getattr(entity, "facility_id", None)
    if facility_id is not None and facility_id != device.facility_id:
        raise ValidationError(
            f"{label} must belong to the same facility as the lab analyzer device"
        )


def filter_specimens_for_device(device):
    return Specimen.objects.filter(facility=device.facility)


def is_context_in_device_facility(ctx, device) -> bool:
    """Return True if all resolved context entities belong to the device's facility."""
    for entity, label in (
        (ctx.specimen, "Specimen"),
        (ctx.encounter, "Encounter"),
        (ctx.service_request, "Service request"),
    ):
        if entity is None:
            continue
        facility_id = getattr(entity, "facility_id", None)
        if facility_id is not None and facility_id != device.facility_id:
            return False
    return True
