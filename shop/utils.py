from functools import wraps
from django.shortcuts import redirect
from django.contrib import messages

from .models import Shop


# ═════════════════════════════════════════════════════════════
# SHOP TENANCY
# ═════════════════════════════════════════════════════════════

def get_user_shop(user):
    """Returns the Shop this user belongs to, or None."""
    if not user.is_authenticated:
        return None
    if hasattr(user, 'profile'):
        return user.profile.shop
    return None


def shop_required(view_func):
    """Ensures the user has a shop assigned. Attaches request.shop."""
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        shop = get_user_shop(request.user)
        if not shop:
            messages.error(request, 'Your account is not linked to any shop. Contact your administrator.')
            return redirect('login')
        request.shop = shop
        return view_func(request, *args, **kwargs)
    return wrapper


# ═════════════════════════════════════════════════════════════
# ROLE-BASED ACCESS CONTROL
# ═════════════════════════════════════════════════════════════

def role_required(*allowed_roles):
    """
    Restrict view to specific roles.

    Usage:
        @role_required('owner')
        def team_list(request): ...

        @role_required('owner', 'admin')
        def reports(request): ...
    """
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return redirect('login')

            if not hasattr(request.user, 'profile'):
                messages.error(request, 'Your account is not linked to any shop.')
                return redirect('login')

            user_role = request.user.profile.role
            if user_role not in allowed_roles:
                messages.error(
                    request,
                    f'Access denied. This page is only available to '
                    f'{", ".join(allowed_roles)}.'
                )
                return redirect('dashboard')

            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator