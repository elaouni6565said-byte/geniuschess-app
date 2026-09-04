import os
import json
import re
import unicodedata
from datetime import date, datetime
from decimal import Decimal

SUPPORTED_LANGUAGES = {
    'fr': {'name': 'Français', 'flag': '🇫🇷', 'dir': 'ltr'},
    'ar': {'name': 'العربية', 'flag': '🇲🇦', 'dir': 'rtl'},
}

DEFAULT_LANGUAGE = 'fr'

_TRANSLATIONS_CACHE = {}

def get_locales_dir():
    current_dir = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(current_dir, 'locales')

def load_translations(force_reload=False):
    global _TRANSLATIONS_CACHE
    if _TRANSLATIONS_CACHE and not force_reload:
        return _TRANSLATIONS_CACHE
    
    locales_dir = get_locales_dir()
    cache = {}
    for lang in ['fr', 'ar']:
        file_path = os.path.join(locales_dir, f'{lang}.json')
        if os.path.exists(file_path):
            with open(file_path, 'r', encoding='utf-8') as f:
                cache[lang] = json.load(f)
        else:
            cache[lang] = {}
    _TRANSLATIONS_CACHE = cache
    return _TRANSLATIONS_CACHE

def get_translation(key_path, lang='fr', default=None, **kwargs):
    translations = load_translations()
    target_lang = lang if lang in SUPPORTED_LANGUAGES else DEFAULT_LANGUAGE
    
    def lookup(data, path):
        keys = path.split('.')
        current = data
        for k in keys:
            if isinstance(current, dict) and k in current:
                current = current[k]
            else:
                return None
        return current
    
    val = lookup(translations.get(target_lang, {}), key_path)
    if val is None and target_lang != DEFAULT_LANGUAGE:
        val = lookup(translations.get(DEFAULT_LANGUAGE, {}), key_path)
        
    if val is None:
        val = default if default is not None else key_path
        
    if isinstance(val, str) and kwargs:
        try:
            return val.format(**kwargs)
        except Exception:
            return val
    return val

def _(key_path, lang='fr', **kwargs):
    return get_translation(key_path, lang=lang, **kwargs)

def get_direction(lang='fr'):
    info = SUPPORTED_LANGUAGES.get(lang, SUPPORTED_LANGUAGES[DEFAULT_LANGUAGE])
    return info['dir']

def is_rtl(lang='fr'):
    return get_direction(lang) == 'rtl'

FRENCH_MONTHS = {
    1: 'janvier', 2: 'février', 3: 'mars', 4: 'avril', 5: 'mai', 6: 'juin',
    7: 'juillet', 8: 'août', 9: 'septembre', 10: 'octobre', 11: 'novembre', 12: 'décembre'
}

ARABIC_MONTHS = {
    1: 'يناير', 2: 'فبراير', 3: 'مارس', 4: 'أبريل', 5: 'ماي', 6: 'يونيو',
    7: 'يوليوز', 8: 'غشت', 9: 'شتنبر', 10: 'أكتوبر', 11: 'نونبر', 12: 'دجنبر'
}

FRENCH_DAYS = {
    0: 'Lundi', 1: 'Mardi', 2: 'Mercredi', 3: 'Jeudi', 4: 'Vendredi', 5: 'Samedi', 6: 'Dimanche'
}

ARABIC_DAYS = {
    0: 'الاثنين', 1: 'الثلاثاء', 2: 'الأربعاء', 3: 'الخميس', 4: 'الجمعة', 5: 'السبت', 6: 'الأحد'
}

def format_date_localized(dt, lang='fr', include_time=False, include_weekday=False):
    if dt is None:
        return ''
    if isinstance(dt, str):
        try:
            dt = datetime.fromisoformat(dt)
        except Exception:
            return dt
            
    day_num = f'{dt.day:02d}'
    year_num = str(dt.year)
    
    if lang == 'ar':
        month_name = ARABIC_MONTHS.get(dt.month, str(dt.month))
        formatted = f'{day_num} {month_name} {year_num}'
        if include_weekday:
            weekday_name = ARABIC_DAYS.get(dt.weekday(), '')
            formatted = f'{weekday_name} {formatted}'
    else:
        month_name = FRENCH_MONTHS.get(dt.month, str(dt.month))
        formatted = f'{day_num} {month_name} {year_num}'
        if include_weekday:
            weekday_name = FRENCH_DAYS.get(dt.weekday(), '')
            formatted = f'{weekday_name} {formatted}'
            
    if include_time and isinstance(dt, (datetime,)):
        time_str = dt.strftime('%H:%M')
        formatted += f' {time_str}'
    return formatted

def format_currency(amount, lang='fr'):
    if amount is None:
        amount = Decimal('0.00')
    if not isinstance(amount, Decimal):
        amount = Decimal(str(amount))
        
    formatted_num = f'{amount:,.2f}'.replace(',', ' ').replace('.', ',')
    currency_label = 'درهم' if lang == 'ar' else 'DH'
    return f'{formatted_num} {currency_label}'

def prepare_arabic_text_for_pdf(text):
    if not text:
        return ''
    has_arabic = any(
        ('\u0600' <= char <= '\u06FF') or 
        ('\u0750' <= char <= '\u077F') or 
        ('\uFB50' <= char <= '\uFDFF') or 
        ('\uFE70' <= char <= '\uFEFF') 
        for char in text
    )
    if not has_arabic:
        return text
    try:
        import arabic_reshaper
        from bidi.algorithm import get_display
        reshaped = arabic_reshaper.reshape(text)
        return get_display(reshaped)
    except Exception:
        return text

def normalize_text_for_search(text):
    if not text:
        return ''
    text = text.lower()
    decomposed = unicodedata.normalize('NFD', text)
    stripped = ''.join(c for c in decomposed if unicodedata.category(c) != 'Mn')
    stripped = re.sub(r'[إأآا]', 'ا', stripped)
    stripped = re.sub(r'ة', 'ه', stripped)
    stripped = re.sub(r'[ىي]', 'ي', stripped)
    stripped = re.sub(r'[\u064B-\u0652\u0670]', '', stripped)
    stripped = re.sub(r'ـ', '', stripped)
    stripped = re.sub(r'\s+', ' ', stripped)
    return stripped.strip()
