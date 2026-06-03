from care.emr.models.device import Device
from care.emr.registries.device_type.device_registry import DeviceTypeBase

from gateway_device.spec import GatewayDeviceReadSpec
from lab_analyzer_device.spec import (
    LabAnalyzerDeviceMetadataReadSpec,
    LabAnalyzerDeviceMetadataWriteSpec,
)


class LabAnalyzerDevice(DeviceTypeBase):
    @classmethod
    def get_gateway_device(cls, obj):
        if gateway_external_id := obj.metadata.get("gateway"):
            return Device.objects.filter(
                external_id=gateway_external_id, care_type="gateway"
            ).first()
        return None

    def _write_metadata(self, request_data, obj):
        validated_data = LabAnalyzerDeviceMetadataWriteSpec(**request_data)
        obj.metadata = validated_data.model_dump(mode="json")
        obj.save(update_fields=["metadata"])
        return obj

    def handle_create(self, request_data, obj):
        return self._write_metadata(request_data, obj)

    def handle_update(self, request_data, obj):
        return self._write_metadata(request_data, obj)

    def list(self, obj):
        return self.retrieve(obj)

    def retrieve(self, obj):
        metadata = obj.metadata
        gateway = self.get_gateway_device(obj)
        metadata["gateway"] = (
            GatewayDeviceReadSpec.serialize(gateway) if gateway else None
        )
        return LabAnalyzerDeviceMetadataReadSpec(**metadata).model_dump(mode="json")
