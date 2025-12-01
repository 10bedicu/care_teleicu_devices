from django.conf import settings
from rest_framework.routers import DefaultRouter, SimpleRouter

from vitals_observation_device.viewsets.automated_observations import (
    AutomatedObservationsViewSet,
)

router = DefaultRouter() if settings.DEBUG else SimpleRouter()

router.register(
    "automated_observations",
    AutomatedObservationsViewSet,
    basename="automated-observations",
)

urlpatterns = router.urls
