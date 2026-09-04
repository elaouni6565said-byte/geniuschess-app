from .i18n import SUPPORTED_LANGUAGES, DEFAULT_LANGUAGE, get_direction

class BilingualMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # 1. Query param check (?lang=fr or ?lang=ar)
        query_lang = request.GET.get('lang')
        if query_lang in SUPPORTED_LANGUAGES:
            selected_lang = query_lang
        elif hasattr(request, 'user') and request.user.is_authenticated and getattr(request.user, 'preferred_language', None):
            selected_lang = request.user.preferred_language
        elif 'gca_language' in request.session:
            selected_lang = request.session['gca_language']
        elif 'gca_language' in request.COOKIES:
            cookie_lang = request.COOKIES['gca_language']
            selected_lang = cookie_lang if cookie_lang in SUPPORTED_LANGUAGES else DEFAULT_LANGUAGE
        else:
            selected_lang = DEFAULT_LANGUAGE

        if selected_lang not in SUPPORTED_LANGUAGES:
            selected_lang = DEFAULT_LANGUAGE

        # Persist in session
        if request.session.get('gca_language') != selected_lang:
            request.session['gca_language'] = selected_lang

        # Save to user model if authenticated and changed
        if hasattr(request, 'user') and request.user.is_authenticated:
            if getattr(request.user, 'preferred_language', None) != selected_lang:
                request.user.preferred_language = selected_lang
                request.user.save(update_fields=['preferred_language'])

        request.LANGUAGE_CODE = selected_lang
        request.LANGUAGE_DIR = get_direction(selected_lang)
        request.IS_RTL = (request.LANGUAGE_DIR == 'rtl')

        # Device mode check (?device=pc or ?device=mobile or ?device=auto)
        query_device = request.GET.get('device')
        if query_device in ('pc', 'mobile', 'auto'):
            selected_device = query_device
        elif 'gca_device_mode' in request.session:
            selected_device = request.session['gca_device_mode']
        elif 'gca_device_mode' in request.COOKIES:
            cookie_device = request.COOKIES['gca_device_mode']
            selected_device = cookie_device if cookie_device in ('pc', 'mobile', 'auto') else 'auto'
        else:
            selected_device = 'auto'

        if request.session.get('gca_device_mode') != selected_device:
            request.session['gca_device_mode'] = selected_device

        request.DEVICE_MODE = selected_device

        response = self.get_response(request)
        
        # Set cookies so they persist across client restarts
        response.set_cookie('gca_language', selected_lang, max_age=365*24*60*60, samesite='Lax')
        response.set_cookie('gca_device_mode', selected_device, max_age=365*24*60*60, samesite='Lax')
        return response
