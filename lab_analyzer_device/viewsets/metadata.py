from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.viewsets import ViewSet

from lab_analyzer_device.astm.devices.registry import registry as astm_registry
from lab_analyzer_device.hl7.devices.registry import registry


class LabAnalyzerMetadataViewSet(ViewSet):
    """Provides metadata about lab analyzer configuration options."""

    permission_classes = (IsAuthenticated,)

    @action(detail=False, methods=["get"])
    def device_types(self, request):
        """Return available lab analyzer device types from the profile registries.

        Each type reports the protocols it supports (``hl7`` and/or ``astm``)
        so the configuration UI can offer a valid protocol per device.
        """
        hl7_profiles = registry.get_profiles()
        astm_profiles = astm_registry.get_profiles()

        types = []
        for device_type, profile in hl7_profiles.items():
            supported = ["hl7"]
            if device_type in astm_profiles:
                supported.append("astm")
            types.append(
                {
                    "id": profile.device_type,
                    "name": profile.display_name,
                    "hl7_version": profile.hl7_version,
                    "communication_mode": profile.communication_mode,
                    "hl7_connection_mode": profile.hl7_connection_mode,
                    "default_oru_port": profile.default_oru_port,
                    "supports_query_orders": profile.supports_query_orders,
                    "supported_protocols": supported,
                    "panel_mappings": profile.panel_mappings,
                    "code_mappings": {
                        key: {
                            "code": mapping.loinc_code,
                            "display": mapping.display,
                            "system": mapping.system,
                        }
                        for key, mapping in profile.code_mappings.items()
                    },
                }
            )

        # Device types that only have an ASTM profile (no HL7 equivalent).
        for device_type, profile in astm_profiles.items():
            if device_type in hl7_profiles:
                continue
            types.append(
                {
                    "id": profile.device_type,
                    "name": profile.display_name,
                    "hl7_version": profile.astm_version,
                    "communication_mode": profile.communication_mode,
                    "astm_connection_mode": profile.astm_connection_mode,
                    "default_oru_port": profile.default_oru_port,
                    **profile.serial_default_fields(),
                    "supports_query_orders": profile.supports_query_orders,
                    "supported_protocols": ["astm"],
                    "panel_mappings": profile.panel_mappings,
                    "code_mappings": {
                        key: {
                            "code": mapping.loinc_code,
                            "display": mapping.display,
                            "system": mapping.system,
                        }
                        for key, mapping in profile.code_mappings.items()
                    },
                }
            )
        return Response({"results": types})
