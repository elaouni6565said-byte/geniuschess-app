from .i18n import (
    SUPPORTED_LANGUAGES, DEFAULT_LANGUAGE, get_direction,
    get_translation, format_currency, format_date_localized
)

def bilingual_context(request):
    lang = getattr(request, 'LANGUAGE_CODE', DEFAULT_LANGUAGE)
    direction = getattr(request, 'LANGUAGE_DIR', 'ltr')
    is_rtl = getattr(request, 'IS_RTL', False)
    
    def translate_helper(key, **kwargs):
        return get_translation(key, lang=lang, **kwargs)
        
    def currency_helper(amount):
        return format_currency(amount, lang=lang)

    def date_helper(dt, include_time=False, include_weekday=False):
        return format_date_localized(dt, lang=lang, include_time=include_time, include_weekday=include_weekday)

    return {
        'CURRENT_LANG': lang,
        'CURRENT_DIR': direction,
        'IS_RTL': is_rtl,
        'CURRENT_DEVICE_MODE': getattr(request, 'DEVICE_MODE', 'auto'),
        'SUPPORTED_LANGUAGES': SUPPORTED_LANGUAGES,
        't': translate_helper,
        'format_currency': currency_helper,
        'format_date': date_helper,
    }
