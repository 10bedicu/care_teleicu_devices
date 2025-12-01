from gateway_device.viewsets.open_id import PublicJWKsView
from rest_framework.routers import DefaultRouter

router = DefaultRouter()

router.register("", PublicJWKsView, basename="public-jwks")

urlpatterns = router.urls
