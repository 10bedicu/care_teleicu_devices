from django.db.models.signals import post_save
from django.db import transaction
from django.dispatch import receiver
from django.utils import timezone

from care.emr.models import FacilityLocation, Device, DeviceEncounterHistory


@receiver(post_save, sender=FacilityLocation)
def unlink_on_encounter_location_changed(sender, instance, created, **kwargs):
    """
    Signal handler to unlink vitals observation device from the encounter
    when the bed (location) is no longer associated with the same encounter
    as the device.
    """
    devices_to_unlink = Device.objects.filter(
        care_type="vitals-observation", current_location=instance
    ).exclude(current_encounter=instance.current_encounter)

    with transaction.atomic():
        for device in devices_to_unlink:
            if device.current_encounter:
                old_obj = DeviceEncounterHistory.objects.filter(
                    device=device, encounter=device.current_encounter, end__isnull=True
                ).first()
                if old_obj:
                    old_obj.end = timezone.now()
                    old_obj.save()
        devices_to_unlink.update(current_encounter=None)
