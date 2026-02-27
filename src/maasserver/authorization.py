# Copyright 2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Utility functions for checking user permissions and reduce the `if rbac.is_enabled` burden over all the places."""

from django.contrib.auth.models import User

from maasserver.openfga import get_openfga_client


def clear_caches():
    from maasserver.rbac import rbac

    rbac.clear()
    get_openfga_client().clear_cache()


def can_edit_global_entities(user: User) -> bool:
    from maasserver.rbac import rbac

    if rbac.is_enabled():
        return user.is_superuser
    return get_openfga_client().can_edit_global_entities(user)


def can_edit_machines(user: User) -> bool:
    from maasserver.rbac import rbac

    if rbac.is_enabled():
        return user.is_superuser
    return get_openfga_client().can_edit_machines(user)


def can_edit_controllers(user: User) -> bool:
    from maasserver.rbac import rbac

    if rbac.is_enabled():
        return user.is_superuser
    return get_openfga_client().can_edit_controllers(user)


def can_view_global_entities(user: User) -> bool:
    from maasserver.rbac import rbac

    if rbac.is_enabled():
        return user.is_superuser
    return get_openfga_client().can_view_global_entities(user)


def can_view_configurations(user: User) -> bool:
    from maasserver.rbac import rbac

    if rbac.is_enabled():
        return user.is_superuser
    return get_openfga_client().can_view_configurations(user)


def can_edit_configurations(user: User) -> bool:
    from maasserver.rbac import rbac

    if rbac.is_enabled():
        return user.is_superuser
    return get_openfga_client().can_edit_configurations(user)


def can_edit_machine_in_pool(user: User, pool_id: int):
    from maasserver.rbac import rbac

    if rbac.is_enabled():
        return user.is_superuser
    return get_openfga_client().can_edit_machines_in_pool(user, pool_id)


def can_view_notifications(user: User):
    from maasserver.rbac import rbac

    if rbac.is_enabled():
        return user.is_superuser
    return get_openfga_client().can_view_notifications(user)


def can_view_ipaddresses(user: User):
    from maasserver.rbac import rbac

    if rbac.is_enabled():
        return user.is_superuser
    return get_openfga_client().can_view_ipaddresses(user)
