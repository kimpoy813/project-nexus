# accounts/signals.py  (or wherever your post_save handler is)
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth.models import User
from .models import Profile

@receiver(post_save, sender=User)
def create_or_update_profile(sender, instance, created, **kwargs):
    """
    Ensure a Profile exists for every saved User.
    Use get_or_create to avoid UNIQUE insertion errors during user.save().
    """
    # if user was just created, create profile if it doesn't exist
    if created:
        Profile.objects.get_or_create(
            user=instance,
            defaults={"full_name": instance.username}
        )
    else:
        # If not created, ensure there's a profile and save it
        profile, _ = Profile.objects.get_or_create(user=instance, defaults={"full_name": instance.username})
        profile.save()