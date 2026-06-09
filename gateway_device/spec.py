from gateway_device.utils import validate_endpoint_address, validate_jwks_url
from pydantic import BaseModel, field_validator

from care.emr.resources.device.spec import DeviceListSpec


class GatewayDeviceReadSpec(DeviceListSpec):
    pass


class GatewayDeviceMetadataReadSpec(BaseModel):
    endpoint_address: str | None = None
    insecure: bool | None = False
    jwks_url: str | None = None


class GatewayDeviceMetadataWriteSpec(BaseModel):
    endpoint_address: str | None = None
    insecure: bool = False
    jwks_url: str | None = None

    @field_validator("endpoint_address", mode="before")
    @classmethod
    def validate_endpoint_address(cls, value):
        if value is None:
            return None
        return validate_endpoint_address(value)

    @field_validator("jwks_url", mode="before")
    @classmethod
    def validate_jwks_url(cls, value):
        if value is None or value == "":
            return None
        return validate_jwks_url(value)
