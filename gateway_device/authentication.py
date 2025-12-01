import logging

import jwt
import requests
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
from drf_spectacular.extensions import OpenApiAuthenticationExtension
from rest_framework import HTTP_HEADER_ENCODING
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import AuthenticationFailed, InvalidToken
from rest_framework_simplejwt.tokens import Token

from care.emr.models import Device
from care.users.models import User

logger = logging.getLogger(__name__)


OPENID_REQUEST_TIMEOUT = 5


def jwk_response_cache_key(url: str) -> str:
    return f"jwk_response:{url}"


class GatewayAuthentication(JWTAuthentication):
    """
    An authentication plugin that authenticates requests through a JSON web
    token provided in a request header.
    """

    gateway_header = "X-Gateway-Id"
    auth_header_type = "Gateway_Bearer"
    auth_header_type_bytes = auth_header_type.encode(HTTP_HEADER_ENCODING)

    def get_public_key(self, url):
        public_key_json = cache.get(jwk_response_cache_key(url))
        if not public_key_json:
            res = requests.get(url, timeout=OPENID_REQUEST_TIMEOUT)
            res.raise_for_status()
            public_key_json = res.json()
            cache.set(jwk_response_cache_key(url), public_key_json, timeout=60 * 5)
        return public_key_json["keys"][0]

    def open_id_authenticate(self, url, token):
        public_key_response = self.get_public_key(url)
        public_key = jwt.algorithms.RSAAlgorithm.from_jwk(public_key_response)
        return jwt.decode(token, key=public_key, algorithms=["RS256"])

    def authenticate_header(self, request):
        return f'{self.auth_header_type} realm="{self.www_authenticate_realm}"'

    def get_user(self, _: Token):
        user, _ = User.objects.get_or_create(
            username="teleicu-gateway",
            defaults={
                "first_name": "TeleICU",
                "last_name": "Gateway",
                "user_type": "gateway",
                "email": "teleicu-gateway@ohc.network",
                "phone_number": "",
                "is_active": False,
            },
        )
        return user

    def authenticate(self, request):
        header = self.get_header(request)
        if header is None:
            return None

        raw_token = self.get_raw_token(header)
        if raw_token is None or self.gateway_header not in request.headers:
            return None

        external_id = request.headers[self.gateway_header]

        try:
            gateway = Device.objects.get(external_id=external_id, care_type="gateway")
        except (Device.DoesNotExist, ValidationError) as e:
            raise InvalidToken(
                {"detail": "Invalid Gateway Device", "messages": []}
            ) from e

        request.gateway = gateway

        if not gateway.metadata and not gateway.metadata.get("endpoint_address"):
            raise InvalidToken({"detail": "Gateway endpoint not configured"})

        protocol = "http" if gateway.metadata.get("insecure", False) else "https"

        open_id_url = (
            f"{protocol}://{gateway.metadata['endpoint_address']}/openid-configuration/"
        )

        validated_token = self.get_validated_token(open_id_url, raw_token)

        return self.get_user(validated_token), validated_token

    def get_raw_token(self, header):
        """
        Extracts an un-validated JSON web token from the given "Authorization"
        header value.
        """
        parts = header.split()

        if len(parts) == 0:
            # Empty AUTHORIZATION header sent
            return None

        if parts[0] != self.auth_header_type_bytes:
            # Assume the header does not contain a JSON web token
            return None

        if len(parts) != 2:  # noqa: PLR2004
            raise AuthenticationFailed(
                _("Authorization header must contain two space-delimited values"),
                code="bad_authorization_header",
            )

        return parts[1]

    def get_validated_token(self, url, raw_token):
        """
        Validates an encoded JSON web token and returns a validated token
        wrapper object.
        """
        try:
            return self.open_id_authenticate(url, raw_token)
        except Exception as e:
            logger.info(e, "Token: ", raw_token)

        raise InvalidToken({"detail": "Given token not valid for any token type"})


class GatewayAuthenticationScheme(OpenApiAuthenticationExtension):
    target_class = "config.authentication.GatewayAuthentication"
    name = "gatewayAuth"

    def get_security_definition(self, auto_schema):
        return {
            "type": "http",
            "scheme": "bearer",
            "bearerFormat": "JWT",
            "description": _(
                "Used for authenticating requests from the Gateway. "
                "The scheme requires a valid JWT token in the Authorization header "
                "The scheme requires a valid JWT token in the Authorization header "
                "along with the facility id in the X-Facility-Id header. "
                "--The value field is just for preview, filling it will show allowed "
                "endpoints.--"
            ),
        }
