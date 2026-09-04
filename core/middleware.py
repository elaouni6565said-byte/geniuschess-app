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

        response = self.get_response(request)
        
        # Set cookie so it persists across client restarts
        response.set_cookie('gca_language', selected_lang, max_age=365*24*60*60, samesite='Lax')
        return response
