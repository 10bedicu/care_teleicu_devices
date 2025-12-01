from logging import Logger

from celery import shared_task
from celery.utils.log import get_task_logger
from django.db.models import Q

from camera_device.models import PositionPreset

logger: Logger = get_task_logger(__name__)


@shared_task
def cleanup_possition_presets():
    """
    Deletes PositionPreset objects whose associated FacilityLocation or Camera device have been deleted.
    """
    logger.info("Cleaning up orphaned PositionPreset objects")
    queryset = PositionPreset.objects.filter(
        Q(location__deleted=True) | Q(camera__deleted=True)
    )
    queryset.update(deleted=True)
