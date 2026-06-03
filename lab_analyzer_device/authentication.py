from rest_framework_simplejwt.tokens import Token

from care.users.models import User
from gateway_device.authentication import GatewayAuthentication


class LabAnalyzerAuthentication(GatewayAuthentication):

    def get_user(self, _: Token):
        user, _ = User.objects.get_or_create(
            username="lab-analyzer-service",
            defaults={
                "first_name": "Lab Analyzer",
                "last_name": "Service",
                "user_type": "gateway",
                "email": "teleicu-gateway@ohc.network",
                "phone_number": "",
                "is_active": False,
            },
        )
        return user
