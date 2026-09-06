from django import template
from django.utils.safestring import mark_safe
from core.i18n import get_translation, format_currency, format_date_localized

register = template.Library()

@register.simple_tag(takes_context=True)
def trans(context, key, **kwargs):
    request = context.get('request')
    lang = getattr(request, 'LANGUAGE_CODE', 'fr') if request else context.get('CURRENT_LANG', 'fr')
    return get_translation(key, lang=lang, **kwargs)

@register.simple_tag(takes_context=True)
def money(context, amount):
    request = context.get('request')
    lang = getattr(request, 'LANGUAGE_CODE', 'fr') if request else context.get('CURRENT_LANG', 'fr')
    return format_currency(amount, lang=lang)

@register.filter(name='currency')
def currency_filter(amount, lang='fr'):
    return format_currency(amount, lang=lang)

@register.simple_tag(takes_context=True)
def local_date(context, dt, include_time=False, include_weekday=False):
    request = context.get('request')
    lang = getattr(request, 'LANGUAGE_CODE', 'fr') if request else context.get('CURRENT_LANG', 'fr')
    return format_date_localized(dt, lang=lang, include_time=include_time, include_weekday=include_weekday)

@register.filter(name='trans_field')
def trans_field(obj, arg='fr'):
    if not obj:
        return ''
        
    parts = str(arg).split(':')
    if len(parts) == 2:
        field_name = parts[0]
        lang = parts[1]
    elif arg in ('fr', 'ar'):
        field_name = None
        lang = arg
    else:
        field_name = arg
        lang = 'fr'

    if field_name:
        if hasattr(obj, 'get_localized'):
            return obj.get_localized(field_name, lang)
        attr_name = f"{field_name}_{lang}"
        if hasattr(obj, attr_name):
            return getattr(obj, attr_name)
        if hasattr(obj, field_name):
            val = getattr(obj, field_name)
            return val() if callable(val) else val
            
    # Default behavior when only language is passed
    if hasattr(obj, 'get_full_name'):
        return obj.get_full_name(lang)
    if hasattr(obj, 'get_name'):
        return obj.get_name(lang)
    if hasattr(obj, 'get_method_label'):
        return obj.get_method_label(lang)
    if hasattr(obj, 'get_period_label'):
        return obj.get_period_label(lang)
    if hasattr(obj, 'get_trainer_name'):
        return obj.get_trainer_name(lang)
    if hasattr(obj, 'get_title'):
        return obj.get_title(lang)
        
    return str(obj)
