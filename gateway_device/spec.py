from gateway_device.utils import validate_endpoint_address
from pydantic import BaseModel, field_validator

from care.emr.resources.device.spec import DeviceListSpec


class GatewayDeviceReadSpec(DeviceListSpec):
    pass


class GatewayDeviceMetadataReadSpec(BaseModel):
    endpoint_address: str | None = None
    insecure: bool | None = False


class GatewayDeviceMetadataWriteSpec(BaseModel):
    endpoint_address: str | None = None
    insecure: bool = False

    @field_validator("endpoint_address", mode="before")
    @classmethod
    def validate_endpoint_address(cls, value):
        if value is None:
            return None
        return validate_endpoint_address(value)
