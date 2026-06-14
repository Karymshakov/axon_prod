from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from .models import Lead, LeadActivity


@receiver(post_save, sender=Lead)
def create_lead_activity_on_create(sender, instance, created, **kwargs):
    """Create activity when a lead is created."""
    if created:
        LeadActivity.objects.create(
            lead=instance,
            activity_type='lead_created',
            description=f'Lead created for {instance.contact_person}',
            metadata={
                'contact_person': instance.contact_person,
                'status': instance.status,
            },
        )


@receiver(pre_save, sender=Lead)
def track_status_change(sender, instance, **kwargs):
    """Track status changes and create activity."""
    if instance.pk:  # Only for existing leads
        try:
            old_lead = Lead.objects.get(pk=instance.pk)
            if old_lead.status != instance.status:
                # Store the old status so we can use it in post_save
                instance._status_changed = True
                instance._old_status = old_lead.status
        except Lead.DoesNotExist:
            pass


@receiver(post_save, sender=Lead)
def create_status_change_activity(sender, instance, created, **kwargs):
    """Create activity for status changes."""
    if not created and hasattr(instance, '_status_changed'):
        old_status_display = dict(Lead.STATUS_CHOICES).get(instance._old_status, instance._old_status)
        new_status_display = dict(Lead.STATUS_CHOICES).get(instance.status, instance.status)

        LeadActivity.objects.create(
            lead=instance,
            activity_type='status_change',
            description=f'Status changed from "{old_status_display}" to "{new_status_display}"',
            metadata={
                'old_status': instance._old_status,
                'new_status': instance.status,
            },
        )

        # Clean up the temporary attributes
        delattr(instance, '_status_changed')
        delattr(instance, '_old_status')


