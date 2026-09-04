from functools import wraps
from django.shortcuts import redirect
from django.contrib import messages
from core.i18n import get_translation

def admin_required(view_func):
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            lang = getattr(request, 'LANGUAGE_CODE', 'fr')
            msg = get_translation('auth.access_restricted', lang=lang)
            messages.warning(request, msg)
            return redirect(f'/login/?next={request.path}')
            
        if not (request.user.is_admin_role() or request.user.is_superuser):
            lang = getattr(request, 'LANGUAGE_CODE', 'fr')
            msg = get_translation('errors.permission_denied', lang=lang)
            messages.error(request, msg)
            return redirect('portal:parent_space' if request.user.is_parent_role() else 'portal:login')
            
        return view_func(request, *args, **kwargs)
    return _wrapped_view
