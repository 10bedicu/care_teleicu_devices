import enum

from care.security.authorization import AuthorizationController, AuthorizationHandler
from care.security.permissions.base import PermissionController
from care.security.permissions.constants import Permission, PermissionContext
from care.security.roles.role import (
    ADMIN_ROLE,
    DOCTOR_ROLE,
    FACILITY_ADMIN_ROLE,
    STAFF_ROLE,
)


class CameraDeviceControlPermissions(enum.Enum):
    can_view_camera_stream = Permission(
        "Can Watch Camera Stream",
        "",
        PermissionContext.FACILITY,
        [STAFF_ROLE, DOCTOR_ROLE, ADMIN_ROLE, FACILITY_ADMIN_ROLE],
    )
    can_control_camera_ptz = Permission(
        "Can Use Camera PTZ Control",
        "",
        PermissionContext.FACILITY,
        [STAFF_ROLE, DOCTOR_ROLE, ADMIN_ROLE, FACILITY_ADMIN_ROLE],
    )


PermissionController.override_permission_handlers.append(CameraDeviceControlPermissions)


class CameraDeviceControlAccess(AuthorizationHandler):
    def can_view_camera_stream(self, user, device):
        org_permission = self.check_permission_in_facility_organization(
            [CameraDeviceControlPermissions.can_view_camera_stream.name],
            user,
            device.facility_organization_cache,
        )
        location_permission = False
        if device.current_location:
            location_permission = self.check_permission_in_facility_organization(
                [CameraDeviceControlPermissions.can_view_camera_stream.name],
                user,
                device.current_location.facility_organization_cache,
            )
        return org_permission or location_permission

    def can_control_camera_ptz(self, user, device):
        org_permission = self.check_permission_in_facility_organization(
            [CameraDeviceControlPermissions.can_control_camera_ptz.name],
            user,
            device.facility_organization_cache,
        )
        location_permission = False
        if device.current_location:
            location_permission = self.check_permission_in_facility_organization(
                [CameraDeviceControlPermissions.can_control_camera_ptz.name],
                user,
                device.current_location.facility_organization_cache,
            )
        return org_permission or location_permission


AuthorizationController.register_internal_controller(CameraDeviceControlAccess)
