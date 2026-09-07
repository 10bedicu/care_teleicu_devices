"""Unit tests for gateway Test Master serialization helpers.

Mocks Django / CARE imports so the helpers can run without a database.
"""

from __future__ import annotations

import sys
import unittest
from types import ModuleType, SimpleNamespace
from unittest.mock import MagicMock
from uuid import uuid4

from pydantic import BaseModel

_django_mock = MagicMock()
_care_mock = MagicMock()

for mod in [
    "django",
    "django.db",
    "django.db.models",
    "django.conf",
    "django.conf.settings",
    "django.core",
    "django.core.exceptions",
    "django.utils",
    "django.utils.timezone",
]:
    sys.modules.setdefault(mod, _django_mock)

for mod in [
    "care",
    "care.emr",
    "care.emr.models",
    "care.emr.models.device",
    "care.emr.resources",
    "care.emr.resources.base",
]:
    sys.modules.setdefault(mod, _care_mock)

_care_mock.emr.resources.base.EMRResource = type(
    "EMRResource",
    (BaseModel,),
    {"__annotations__": {}},
)

# Provide a real pydantic model so LabAnalyzerDeviceMetadataReadSpec can build.
_gateway_spec = ModuleType("gateway_device.spec")


class GatewayDeviceReadSpec(BaseModel):
    id: str | None = None


_gateway_spec.GatewayDeviceReadSpec = GatewayDeviceReadSpec

_gateway_utils = ModuleType("gateway_device.utils")
_gateway_utils.validate_endpoint_address = lambda value: value

_gateway_pkg = ModuleType("gateway_device")
_gateway_pkg.spec = _gateway_spec
_gateway_pkg.utils = _gateway_utils

sys.modules["gateway_device"] = _gateway_pkg
sys.modules["gateway_device.spec"] = _gateway_spec
sys.modules["gateway_device.utils"] = _gateway_utils

_lab_models = ModuleType("lab_analyzer_device.models")
_lab_models.DeviceActivityDefinition = type("DeviceActivityDefinition", (), {})
_lab_models.LabMessage = type("LabMessage", (), {})
sys.modules["lab_analyzer_device.models"] = _lab_models
sys.modules["lab_analyzer_device.models.device_activity_definition"] = ModuleType(
    "lab_analyzer_device.models.device_activity_definition"
)
sys.modules["lab_analyzer_device.models.message"] = ModuleType(
    "lab_analyzer_device.models.message"
)

from lab_analyzer_device.spec import (  # noqa: E402
    serialize_gateway_activity_definition,
    serialize_gateway_observation_definition,
)


def _od(
    *,
    pk: int,
    title: str = "CBC panel",
    code: str = "58410-2",
    components: list | None = None,
):
    return SimpleNamespace(
        id=pk,
        external_id=uuid4(),
        slug=f"f-facility-cbc-{pk}",
        title=title,
        status="active",
        category="laboratory",
        code={
            "system": "http://loinc.org",
            "code": code,
            "display": title,
        },
        permitted_data_type="quantity",
        permitted_unit=None,
        component=components
        if components is not None
        else [
            {
                "code": {
                    "system": "http://loinc.org",
                    "code": "6690-2",
                    "display": "Leukocytes",
                },
                "permitted_data_type": "quantity",
                "permitted_unit": {
                    "system": "http://unitsofmeasure.org",
                    "code": "10*3/uL",
                    "display": "10^3/uL",
                },
                "qualified_ranges": [],
            }
        ],
    )


def _ad(*, pk: int, od_ids: list[int], title: str = "CBC panel"):
    return SimpleNamespace(
        id=pk,
        external_id=uuid4(),
        slug=f"f-facility-cbc-ad-{pk}",
        title=title,
        status="active",
        classification="laboratory",
        code={
            "system": "http://loinc.org",
            "code": "58410-2",
            "display": title,
        },
        observation_result_requirements=od_ids,
    )


class GatewayObservationDefinitionSerializationTests(unittest.TestCase):
    def test_serializes_parameters_from_component(self):
        od = _od(pk=1)
        result = serialize_gateway_observation_definition(od)

        self.assertEqual(result["title"], "CBC panel")
        self.assertEqual(result["code"]["code"], "58410-2")
        self.assertEqual(len(result["parameters"]), 1)
        self.assertEqual(result["parameters"][0]["code"]["code"], "6690-2")
        self.assertEqual(
            result["parameters"][0]["permitted_unit"]["code"], "10*3/uL"
        )

    def test_handles_missing_component(self):
        od = _od(pk=2, components=[])
        od.component = None
        result = serialize_gateway_observation_definition(od)
        self.assertEqual(result["parameters"], [])


class GatewayActivityDefinitionSerializationTests(unittest.TestCase):
    def test_nests_observation_definitions(self):
        od = _od(pk=10)
        ad = _ad(pk=1, od_ids=[10])
        result = serialize_gateway_activity_definition(ad, {10: od})

        self.assertEqual(result["classification"], "laboratory")
        self.assertEqual(len(result["observation_definitions"]), 1)
        nested = result["observation_definitions"][0]
        self.assertEqual(nested["code"]["code"], "58410-2")
        self.assertEqual(nested["parameters"][0]["code"]["code"], "6690-2")

    def test_skips_missing_observation_definition_ids(self):
        ad = _ad(pk=2, od_ids=[99])
        result = serialize_gateway_activity_definition(ad, {})
        self.assertEqual(result["observation_definitions"], [])


if __name__ == "__main__":
    unittest.main()
