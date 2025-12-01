from camera_device.spec import (
    CameraDeviceMetadataWriteSpec,
    CameraDeviceMetadataReadSpec,
)
from care.emr.models.device import Device
from care.emr.registries.device_type.device_registry import DeviceTypeBase
from gateway_device.spec import GatewayDeviceReadSpec


class CameraDevice(DeviceTypeBase):
    @classmethod
    def get_gateway_device(cls, obj):
        if gateway_external_id := obj.metadata.get("gateway"):
            return Device.objects.filter(
                external_id=gateway_external_id, care_type="gateway"
            ).first()
        return None

    def handle_create(self, request_data, obj):
        validated_data = CameraDeviceMetadataWriteSpec(**request_data)
        obj.metadata = validated_data.model_dump(mode="json")
        obj.save(update_fields=["metadata"])
        return obj

    def handle_update(self, request_data, obj):
        validated_data = CameraDeviceMetadataWriteSpec(**request_data)
        obj.metadata = validated_data.model_dump(mode="json")
        obj.save(update_fields=["metadata"])
        return obj

    def list(self, obj):
        return self.retrieve(obj)

    def retrieve(self, obj):
        metadata = obj.metadata
        gateway = self.get_gateway_device(obj)
        metadata["gateway"] = GatewayDeviceReadSpec.serialize(gateway) if gateway else None
        return CameraDeviceMetadataReadSpec(**metadata).model_dump(mode="json")

    def perform_action(self, obj, action, request):
        return  # Return an HTTP Response
