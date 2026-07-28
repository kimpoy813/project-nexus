"""
Shared helpers for building test users.

A post-save signal creates a FACULTY ``Profile`` whenever a ``User`` is
created, so assigning a different role means updating that existing row and
then re-fetching the user. Doing it by hand is easy to get wrong: the cached
``user.profile`` still reports the old role and permission helpers silently
return the wrong answer. ``make_user`` handles this correctly in one place.
"""

from django.contrib.auth import get_user_model
from django.test import Client

from accounts.models import Profile


User = get_user_model()

DEFAULT_PASSWORD = "test-pass-12345"


def make_user(username, role=Profile.ROLE_FACULTY, *, password=DEFAULT_PASSWORD, **profile_fields):
    """Create a user with ``role`` and return the re-fetched instance.

    Extra keyword arguments (``campus``, ``department``, ``full_name``...) are
    applied to the profile.
    """
    user = User.objects.create_user(
        username=username,
        email=f"{username}@example.com",
        password=password,
    )

    defaults = {"role": role, "email_verified": True}
    defaults.update(profile_fields)
    Profile.objects.update_or_create(user=user, defaults=defaults)

    # Re-fetch so ``user.profile`` reflects the role we just assigned rather
    # than the FACULTY row the signal created.
    return User.objects.get(pk=user.pk)


def make_client(user):
    """Return a ``Client`` already logged in as ``user``."""
    client = Client()
    client.force_login(user)
    return client


def make_user_and_client(username, role=Profile.ROLE_FACULTY, **profile_fields):
    user = make_user(username, role, **profile_fields)
    return user, make_client(user)


# Convenience shorthands for the roles used across the suite.
def admin(username="t_admin", **kw):
    return make_user_and_client(username, Profile.ROLE_ADMIN, **kw)


def director(username="t_director", **kw):
    return make_user_and_client(username, Profile.ROLE_DIRECTOR, **kw)


def staff(username="t_staff", **kw):
    return make_user_and_client(username, Profile.ROLE_STAFF, **kw)


def evaluator(username="t_evaluator", **kw):
    return make_user_and_client(username, Profile.ROLE_EVALUATOR, **kw)


def faculty(username="t_faculty", **kw):
    return make_user_and_client(username, Profile.ROLE_FACULTY, **kw)


def department_coordinator(username="t_deptcoord", **kw):
    kw.setdefault("department", "Computer Science")
    return make_user_and_client(username, Profile.ROLE_DEPARTMENT_COORDINATOR, **kw)


def campus_coordinator(username="t_campcoord", **kw):
    kw.setdefault("campus", "Main Campus")
    return make_user_and_client(username, Profile.ROLE_CAMPUS_COORDINATOR, **kw)
