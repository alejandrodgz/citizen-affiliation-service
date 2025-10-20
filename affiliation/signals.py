from django.db.models.signals import post_save
from django.dispatch import receiver
from affiliation.models import Citizen
from affiliation.rabbitmq.publisher import publish_affiliation_created


@receiver(post_save, sender=Citizen)
def citizen_post_save(sender, instance, created, **kwargs):
    """Signal handler to publish RabbitMQ event when citizen is affiliated (registered)."""
    import logging

    logger = logging.getLogger(__name__)

    print(
        f"🔔 [Signal] Citizen post_save fired - created={created}, is_registered={instance.is_registered}, id={instance.citizen_id}"
    )

    if created and instance.is_registered:
        # Only publish when a new citizen is successfully affiliated/registered
        # Convert citizen_id to int (it's stored as string in DB)
        try:
            id_citizen = int(instance.citizen_id)
            print(f"📤 [Signal] Publishing affiliation.created event for citizen {id_citizen}")
            publish_affiliation_created(id_citizen)
        except (ValueError, TypeError) as e:
            logger.error(
                f"Failed to publish affiliation.created event: Invalid citizen_id {instance.citizen_id} - {str(e)}"
            )
            print(f"❌ [Signal] Failed to publish event: {str(e)}")
    else:
        print(
            f"⏭️  [Signal] Skipping event publish - created={created}, is_registered={instance.is_registered}"
        )
