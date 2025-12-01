from drf_spectacular.utils import extend_schema
from pydantic import BaseModel
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.viewsets import GenericViewSet

from camera_device.spec import PTZPayloadSpec
from care.emr.models.device import Device
from care.security.authorization import AuthorizationController
from rest_framework.exceptions import PermissionDenied
from gateway_device.client import GatewayClient

class GotoPresetRequestSpec(BaseModel):
    preset: int | None


class CameraActionsViewSet(GenericViewSet):
    queryset = Device.objects.filter(care_type="camera")
    lookup_field = "external_id"

    def get_gateway_request_data(self, instance, *args, **kwargs):
        metadata = instance.metadata
        try:
            hostname = metadata["endpoint_address"]
            username = metadata["username"]
            password = metadata["password"]
        except KeyError as e:
            raise ValidationError({key: "Not configured" for key in e.args}) from e
        return {
            "hostname": hostname,
            "port": 80,
            "username": username,
            "password": password,
            **kwargs,
        }

    def get_gateway_client(self, instance):
        metadata = instance.metadata

        try:
            gateway_external_id = metadata["gateway"]
            gateway_device = Device.objects.get(
                external_id=gateway_external_id, care_type="gateway"
            )
        except KeyError as e:
            raise ValidationError({key: "Not configured" for key in e.args}) from e
        except Device.DoesNotExist as e:
            raise ValidationError("Gateway not found") from e

        return GatewayClient(gateway_device)

    def authorize_video_stream(self, instance):
        if not AuthorizationController.call(
            "can_view_camera_stream", self.request.user, instance
        ):
            raise PermissionDenied("You do not have permission to view video stream")

    def authorize_device_control(self, instance):
        if not AuthorizationController.call(
            "can_control_camera_ptz", self.request.user, instance
        ):
            raise PermissionDenied("You do not have permission to control device")

    @action(detail=True, methods=["GET"])
    def get_status(self, request, *args, **kwargs):
        instance = self.get_object()
        self.authorize_video_stream(instance)
        gateway_client = self.get_gateway_client(instance)
        request_data = self.get_gateway_request_data(instance)
        return gateway_client.get("/status", request_data, as_http_response=True)

    @action(detail=True, methods=["GET"])
    def get_presets(self, request, *args, **kwargs):
        instance = self.get_object()
        self.authorize_video_stream(instance)
        gateway_client = self.get_gateway_client(instance)
        request_data = self.get_gateway_request_data(instance)
        return gateway_client.get("/presets", request_data, as_http_response=True)

    @extend_schema(request=GotoPresetRequestSpec)
    @action(detail=True, methods=["POST"])
    def goto_preset(self, request, *args, **kwargs):
        instance = self.get_object()
        self.authorize_device_control(instance)
        gateway_client = self.get_gateway_client(instance)
        validated_data = GotoPresetRequestSpec(**request.data).model_dump(mode="json")
        request_data = self.get_gateway_request_data(instance, **validated_data)
        return gateway_client.post("/gotoPreset", request_data, as_http_response=True)

    @extend_schema(request=PTZPayloadSpec)
    @action(detail=True, methods=["POST"])
    def absolute_move(self, request, *args, **kwargs):
        instance = self.get_object()
        self.authorize_device_control(instance)
        gateway_client = self.get_gateway_client(instance)
        validated_data = PTZPayloadSpec(**request.data).model_dump(mode="json")
        request_data = self.get_gateway_request_data(instance, **validated_data)
        return gateway_client.post("/absoluteMove", request_data, as_http_response=True)

    @extend_schema(request=PTZPayloadSpec)
    @action(detail=True, methods=["POST"])
    def relative_move(self, request, *args, **kwargs):
        instance = self.get_object()
        self.authorize_device_control(instance)
        gateway_client = self.get_gateway_client(instance)
        validated_data = PTZPayloadSpec(**request.data).model_dump(mode="json")
        request_data = self.get_gateway_request_data(instance, **validated_data)
        return gateway_client.post("/relativeMove", request_data, as_http_response=True)

    @action(detail=True, methods=["GET"])
    def stream_token(self, request, *args, **kwargs):
        instance = self.get_object()
        self.authorize_video_stream(instance)
        gateway_client = self.get_gateway_client(instance)
        try:
            metadata = instance.metadata
            request_data = {
                "stream": metadata["stream_id"],
                "ip": metadata["endpoint_address"],
            }
        except KeyError as e:
            raise ValidationError({key: "Not configured" for key in e.args}) from e
        return gateway_client.post(
            "/getToken/videoFeed", request_data, as_http_response=True
        )
