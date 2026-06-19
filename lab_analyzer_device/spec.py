from typing import Literal

from pydantic import BaseModel, UUID4, field_validator, model_validator

from care.emr.models import ActivityDefinition
from care.emr.models.device import Device
from care.emr.resources.base import EMRResource
from gateway_device.spec import GatewayDeviceReadSpec
from gateway_device.utils import validate_endpoint_address

from lab_analyzer_device.models import DeviceActivityDefinition, LabMessage


def _known_device_types() -> set[str]:
    """Collect all device type identifiers from the HL7 and ASTM registries."""
    from lab_analyzer_device.astm.devices.registry import registry as astm_registry
    from lab_analyzer_device.hl7.devices.registry import registry as hl7_registry

    return set(hl7_registry.get_profiles()) | set(astm_registry.get_profiles())


OrmMode = Literal["shared", "client", "server"]
Hl7ConnectionMode = Literal["inbound", "outbound"]
AstmConnectionMode = Literal["inbound", "outbound"]
Transport = Literal["ethernet", "serial"]
Protocol = Literal["hl7", "astm"]
Parity = Literal["N", "E", "O", "M", "S"]
FlowControl = Literal["none", "xonxoff", "rtscts"]


class SerialSettingsSpec(BaseModel):
    serial_port: str | None = None  # e.g. "/dev/ttyUSB0" or "COM3"
    baud_rate: int = 9600
    data_bits: int = 8
    parity: Parity = "N"
    stop_bits: float = 1
    flow_control: FlowControl = "none"


class LabAnalyzerDeviceMetadataReadSpec(BaseModel):
    type: str = "generic"
    gateway: GatewayDeviceReadSpec | None = None
    transport: Transport = "ethernet"
    protocol: Protocol = "hl7"
    endpoint_address: str | None = None
    oru_port: int | None = 2575
    orm_port: int | None = None  # only used when orm_mode="client"
    orm_mode: OrmMode = "shared"
    hl7_connection_mode: Hl7ConnectionMode = "inbound"
    astm_connection_mode: AstmConnectionMode = "outbound"
    # Serial (RS232) line settings — only used when transport="serial"
    serial_port: str | None = None
    baud_rate: int | None = 9600
    data_bits: int | None = 8
    parity: Parity | None = "N"
    stop_bits: float | None = 1
    flow_control: FlowControl | None = "none"
    panel_mappings: dict[str, str | list[str]] | None = None
    code_mappings: dict[str, dict] | None = None

    @field_validator("stop_bits", mode="before")
    @classmethod
    def validate_stop_bits(cls, value):
        if value is None:
            return None
        if isinstance(value, dict) and "parsedValue" in value:
            return float(value["parsedValue"])
        if isinstance(value, dict) and "source" in value:
            return float(value["source"])
        try:
            return float(value)
        except (TypeError, ValueError):
            return 1.0

    @model_validator(mode="after")
    def apply_hl7_profile_defaults(self):
        if self.protocol != "hl7":
            return self
        from lab_analyzer_device.hl7.devices.registry import registry

        profile = registry.get_profile(self.type)
        if self.hl7_connection_mode == "inbound" and profile.hl7_connection_mode != "inbound":
            self.hl7_connection_mode = profile.hl7_connection_mode
        if self.oru_port in (None, 2575) and profile.default_oru_port != 2575:
            self.oru_port = profile.default_oru_port
        return self

    @model_validator(mode="after")
    def apply_astm_profile_defaults(self):
        if self.protocol != "astm":
            return self
        from lab_analyzer_device.astm.devices.registry import registry as astm_registry

        profile = astm_registry.get_profile(self.type)
        if self.astm_connection_mode == "outbound" and profile.astm_connection_mode != "outbound":
            self.astm_connection_mode = profile.astm_connection_mode
        if self.oru_port in (None, 2575) and profile.default_oru_port != 2575:
            self.oru_port = profile.default_oru_port
        return self


class LabAnalyzerDeviceMetadataWriteSpec(BaseModel):
    type: str = "generic"
    gateway: UUID4 | None = None
    transport: Transport = "ethernet"
    protocol: Protocol = "hl7"
    endpoint_address: str | None = None
    oru_port: int | None = 2575
    orm_port: int | None = None  # only used when orm_mode="client"
    orm_mode: OrmMode = "shared"
    hl7_connection_mode: Hl7ConnectionMode | None = None
    astm_connection_mode: AstmConnectionMode | None = None
    # Serial (RS232) line settings — only used when transport="serial"
    serial_port: str | None = None
    baud_rate: int | None = 9600
    data_bits: int | None = 8
    parity: Parity | None = "N"
    stop_bits: float | None = 1
    flow_control: FlowControl | None = "none"
    panel_mappings: dict[str, str | list[str]] | None = None
    code_mappings: dict[str, dict] | None = None

    @field_validator("type", mode="before")
    @classmethod
    def validate_device_type(cls, value):
        known = _known_device_types()
        if value not in known:
            raise ValueError(
                f"Unknown device type '{value}'. "
                f"Available types: {', '.join(sorted(known))}"
            )
        return value

    @field_validator("stop_bits", mode="before")
    @classmethod
    def validate_stop_bits(cls, value):
        if value is None:
            return None
        if isinstance(value, dict) and "parsedValue" in value:
            return float(value["parsedValue"])
        if isinstance(value, dict) and "source" in value:
            return float(value["source"])
        try:
            return float(value)
        except (TypeError, ValueError):
            return 1.0

    @field_validator("gateway", mode="before")
    @classmethod
    def validate_gateway(cls, value):
        if value is None:
            return value
        try:
            Device.objects.get(external_id=value, care_type="gateway")
        except Device.DoesNotExist:
            raise ValueError("Gateway device does not exist")
        return value

    @field_validator("endpoint_address", mode="before")
    @classmethod
    def validate_endpoint_address(cls, value):
        if value is None:
            return None
        return validate_endpoint_address(value)

    def _profile_communication_mode(self) -> str:
        """Resolve the device's communication mode for the chosen protocol."""
        if self.protocol == "astm":
            from lab_analyzer_device.astm.devices.registry import registry as astm_registry

            return astm_registry.get_profile(self.type).communication_mode
        from lab_analyzer_device.hl7.devices.registry import registry

        return registry.get_profile(self.type).communication_mode

    def _hl7_profile(self):
        from lab_analyzer_device.hl7.devices.registry import registry

        return registry.get_profile(self.type)

    def _astm_profile(self):
        from lab_analyzer_device.astm.devices.registry import registry as astm_registry

        return astm_registry.get_profile(self.type)

    @model_validator(mode="after")
    def apply_hl7_profile_defaults(self):
        if self.protocol != "hl7":
            return self
        profile = self._hl7_profile()
        if self.hl7_connection_mode is None:
            self.hl7_connection_mode = profile.hl7_connection_mode
        if self.oru_port is None or (
            self.oru_port == 2575 and profile.default_oru_port != 2575
        ):
            self.oru_port = profile.default_oru_port
        if self.hl7_connection_mode == "outbound":
            self.orm_mode = "shared"
            self.orm_port = None
        return self

    @model_validator(mode="after")
    def apply_astm_profile_defaults(self):
        if self.protocol != "astm":
            return self
        profile = self._astm_profile()
        if self.astm_connection_mode is None:
            self.astm_connection_mode = profile.astm_connection_mode
        if self.oru_port is None or (
            self.oru_port == 2575 and profile.default_oru_port != 2575
        ):
            self.oru_port = profile.default_oru_port
        if self.transport == "serial":
            if self.baud_rate is None or self.baud_rate == 9600:
                self.baud_rate = profile.default_baud_rate
            if self.data_bits is None or self.data_bits == 8:
                self.data_bits = profile.default_data_bits
            if self.parity is None or self.parity == "N":
                self.parity = profile.default_parity
            if self.stop_bits is None or self.stop_bits == 1:
                self.stop_bits = profile.default_stop_bits
            if self.flow_control is None or self.flow_control == "none":
                self.flow_control = profile.default_flow_control
        return self

    @model_validator(mode="after")
    def validate_transport(self):
        if self.transport == "serial":
            if not self.serial_port:
                raise ValueError("serial_port is required when transport is 'serial'")
            # Serial links are point-to-point and bidirectional over one port;
            # network addressing/ports do not apply.
            self.endpoint_address = None
            self.oru_port = None
            self.orm_port = None
        else:
            # Clear serial port settings
            self.serial_port = None
            self.baud_rate = None
            self.data_bits = None
            self.parity = None
            self.stop_bits = None
            self.flow_control = None
        return self

    @model_validator(mode="after")
    def validate_orm_port(self):
        # Unidirectional devices don't use order communication
        if self._profile_communication_mode() == "unidirectional":
            self.orm_port = None
            self.orm_mode = "shared"
            return self

        # Serial ordering rides the single always-open link (shared semantics).
        if self.transport == "serial":
            self.orm_mode = "shared"
            self.orm_port = None
            return self

        # Outbound HL7: gateway dials the analyzer; worklist/results share the link.
        if self.protocol == "hl7" and self.hl7_connection_mode == "outbound":
            self.orm_mode = "shared"
            self.orm_port = None
            return self

        if self.transport == "ethernet" and not self.endpoint_address:
            raise ValueError("endpoint_address is required when transport is 'ethernet'")

        if self.orm_mode in ("client", "server") and self.orm_port is None:
            raise ValueError("orm_port is required when orm_mode is 'client' or 'server'")
        if self.orm_mode == "shared":
            self.orm_port = None
        return self


class DeviceActivityDefinitionReadSpec(EMRResource):
    __model__ = DeviceActivityDefinition
    __exclude__ = ["device", "activity_definition"]

    id: UUID4
    device_id: UUID4
    activity_definition_id: UUID4
    activity_definition_title: str
    activity_definition_code: dict | None = None

    @classmethod
    def perform_extra_serialization(cls, mapping, obj, *args, **kwargs):
        mapping["id"] = obj.external_id
        mapping["device_id"] = obj.device.external_id
        mapping["activity_definition_id"] = obj.activity_definition.external_id
        mapping["activity_definition_title"] = obj.activity_definition.title
        mapping["activity_definition_code"] = obj.activity_definition.code


class DeviceActivityDefinitionCreateSpec(EMRResource):
    __model__ = DeviceActivityDefinition
    __exclude__ = ["device", "activity_definition"]

    device_external_id: UUID4
    activity_definition_external_id: UUID4

    def perform_extra_deserialization(self, is_update, obj):
        obj.device = Device.objects.get(
            external_id=self.device_external_id,
            care_type="lab-analyzer",
        )
        obj.activity_definition = ActivityDefinition.objects.get(
            external_id=self.activity_definition_external_id,
        )
        if obj.activity_definition.facility_id != obj.device.facility_id:
            raise ValueError(
                "Activity definition must belong to the same facility as the device"
            )


class LabMessageReadSpec(EMRResource):
    __model__ = LabMessage
    __exclude__ = ["device", "patient", "encounter", "specimen"]

    id: UUID4
    device_id: UUID4
    patient_id: UUID4 | None = None
    encounter_id: UUID4 | None = None
    message_type: str
    message_control_id: str
    raw_message: str
    parsed_data: dict
    status: str
    error_details: str | None = None

    @classmethod
    def perform_extra_serialization(cls, mapping, obj, *args, **kwargs):
        mapping["id"] = obj.external_id
        mapping["device_id"] = obj.device.external_id
        mapping["patient_id"] = obj.patient.external_id if obj.patient else None
        mapping["encounter_id"] = obj.encounter.external_id if obj.encounter else None
