import os

os.makedirs('core/templatetags', exist_ok=True)
with open('core/templatetags/__init__.py', 'w', encoding='utf-8') as f:
    pass

content = """from django import template
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

@register.simple_tag(takes_context=True)
def local_date(context, dt, include_time=False, include_weekday=False):
    request = context.get('request')
    lang = getattr(request, 'LANGUAGE_CODE', 'fr') if request else context.get('CURRENT_LANG', 'fr')
    return format_date_localized(dt, lang=lang, include_time=include_time, include_weekday=include_weekday)

@register.filter(name='trans_field')
def trans_field(obj, field_prefix_and_lang):
    parts = field_prefix_and_lang.split(':')
    prefix = parts[0]
    lang = parts[1] if len(parts) > 1 else 'fr'
    
    if hasattr(obj, 'get_localized'):
        return obj.get_localized(prefix, lang)
        
    attr_name = f"{prefix}_{lang}"
    if hasattr(obj, attr_name):
        return getattr(obj, attr_name)
    fallback_attr = f"{prefix}_fr"
    if hasattr(obj, fallback_attr):
        return getattr(obj, fallback_attr)
    return getattr(obj, prefix, '')
"""

with open('core/templatetags/gca_tags.py', 'w', encoding='utf-8') as f:
    f.write(content)

print("Created core/templatetags/gca_tags.py")
