from celery import Celery, current_app
from celery.schedules import crontab

from camera_device.tasks.cleanup_possition_presets import (
    cleanup_possition_presets,
)


@current_app.on_after_finalize.connect
def setup_periodic_tasks(sender: Celery, **kwargs):
    sender.add_periodic_task(
        crontab(hour="0", minute="0"),
        cleanup_possition_presets.s(),
        name="cleanup_possition_presets",
    )
