from lab_analyzer_device.hl7.devices.base import DeviceHL7Profile, LoincMapping
from lab_analyzer_device.hl7.devices.registry import registry


class GenericDeviceProfile(DeviceHL7Profile):
    """
    Generic HL7 v2.3 device profile.

    Handles standard ORU^R01 / ORM^O01 messages.
    Used as fallback for unknown analyzer models.
    """

    @property
    def device_type(self) -> str:
        return "generic"

    @property
    def display_name(self) -> str:
        return "Generic Lab Analyzer"

    @property
    def code_mappings(self) -> dict[str, LoincMapping]:
        return {
            "TSH_1": LoincMapping("3016-3", "Thyrotropin [Units/volume] in Serum or Plasma"),
            "GLU": LoincMapping("2345-7", "Glucose [Mass/volume] in Serum or Plasma"),
            "HGB": LoincMapping("718-7", "Hemoglobin [Mass/volume] in Blood"),
            "WBC": LoincMapping("6690-2", "Leukocytes [#/volume] in Blood"),
            "RBC": LoincMapping("789-8", "Erythrocytes [#/volume] in Blood"),
            "PLT": LoincMapping("777-3", "Platelets [#/volume] in Blood"),
            "CRE": LoincMapping("2160-0", "Creatinine [Mass/volume] in Serum or Plasma"),
            "BUN": LoincMapping("3094-0", "Urea nitrogen [Mass/volume] in Serum or Plasma"),
            "ALT": LoincMapping("1742-6", "Alanine aminotransferase [Enzymatic activity/volume] in Serum or Plasma"),
            "AST": LoincMapping("1920-8", "Aspartate aminotransferase [Enzymatic activity/volume] in Serum or Plasma"),
        }


registry.register(GenericDeviceProfile)
