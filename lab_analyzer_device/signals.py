from django.db.models.signals import post_save
from django.dispatch import receiver

from care.emr.models.specimen import Specimen


@receiver(post_save, sender=Specimen)
def set_accession_identifier_to_id(sender, instance, created, **kwargs):
    """Use the database ID as a shorter accession fallback for device compatibility.

    CARE defaults ``accession_identifier`` to ``external_id`` when no explicit
    accession value is provided. In our flow, ``external_id`` is typically a UUID,
    and some lab analyzer devices do not accept such long identifiers. When that
    defaulting behavior happens on creation, we replace the accession identifier
    with the specimen's database ID so downstream devices receive a shorter,
    device-compatible value.
    """
    if created and str(instance.accession_identifier) == str(instance.external_id):
        Specimen.objects.filter(pk=instance.pk).update(
            accession_identifier=str(instance.id)
        )
        instance.accession_identifier = str(instance.id)
