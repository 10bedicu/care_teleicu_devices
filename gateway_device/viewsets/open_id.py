from django.conf import settings
from django.utils.decorators import method_decorator
from django.views.decorators.cache import cache_page
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.viewsets import GenericViewSet


class PublicJWKsView(GenericViewSet):
    """
    Retrieve the OpenID Connect configuration
    """

    authentication_classes = ()
    permission_classes = ()

    @method_decorator(cache_page(60 * 60 * 24))
    @action(detail=False, methods=["GET"], url_path="jwks.json")
    def jwks(self, *args, **kwargs):
        return Response(settings.JWKS.as_dict())
