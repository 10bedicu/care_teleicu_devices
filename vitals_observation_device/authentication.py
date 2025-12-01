from rest_framework_simplejwt.tokens import Token

from care.users.models import User
from gateway_device.authentication import GatewayAuthentication


class AutomatedObservationsAuthentication(GatewayAuthentication):

    def get_user(self, _: Token):
        user, _ = User.objects.get_or_create(
            username="automated-observations",
            defaults={
                "first_name": "Automated",
                "last_name": "Observations",
                "user_type": "gateway",
                "email": "teleicu-gateway@ohc.network",
                "phone_number": "",
                "is_active": False,
            },
        )
        return user
