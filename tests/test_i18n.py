import pytest
import json
import os
from decimal import Decimal
from datetime import date, datetime
from core.i18n import (
    load_translations, get_translation, get_direction, is_rtl,
    format_currency, format_date_localized, prepare_arabic_text_for_pdf,
    normalize_text_for_search, SUPPORTED_LANGUAGES
)

def test_translation_dictionaries_symmetry():
    """Ensures fr.json and ar.json have identical key structures without missing keys (47.22 & 47.23)."""
    trans = load_translations(force_reload=True)
    assert 'fr' in trans
    assert 'ar' in trans
    
    def extract_keys(d, prefix=''):
        keys = set()
        for k, v in d.items():
            full_key = f"{prefix}.{k}" if prefix else k
            if isinstance(v, dict):
                keys.update(extract_keys(v, full_key))
            else:
                keys.add(full_key)
        return keys

    fr_keys = extract_keys(trans['fr'])
    ar_keys = extract_keys(trans['ar'])

    missing_in_ar = fr_keys - ar_keys
    missing_in_fr = ar_keys - fr_keys

    assert not missing_in_ar, f"Keys missing in Arabic dictionary: {missing_in_ar}"
    assert not missing_in_fr, f"Keys missing in French dictionary: {missing_in_fr}"

def test_directionality():
    """Checks LTR/RTL resolution (47.4 & 47.5)."""
    assert get_direction('fr') == 'ltr'
    assert get_direction('ar') == 'rtl'
    assert is_rtl('ar') is True
    assert is_rtl('fr') is False

def test_format_currency():
    """Checks real numeric amounts and proper currency suffixes (47.18)."""
    amount = Decimal('100.00')
    assert '100,00 DH' == format_currency(amount, lang='fr')
    assert '100,00 درهم' == format_currency(amount, lang='ar')
    
    large_amount = Decimal('1250.50')
    assert '1 250,50 DH' == format_currency(large_amount, lang='fr')
    assert '1 250,50 درهم' == format_currency(large_amount, lang='ar')

def test_format_date_localized():
    """Checks localized month and day names (47.8 & 47.17)."""
    d = date(2026, 9, 3) # Thursday 03 September 2026
    fr_date = format_date_localized(d, lang='fr', include_weekday=True)
    ar_date = format_date_localized(d, lang='ar', include_weekday=True)

    assert 'Jeudi' in fr_date
    assert 'septembre' in fr_date
    assert '2026' in fr_date

    assert 'الخميس' in ar_date
    assert 'شتنبر' in ar_date
    assert '2026' in ar_date

def test_arabic_pdf_reshaping():
    """Checks Arabic text shaping for ReportLab (47.7 & 47.19)."""
    text = "وصل الأداء"
    prepared = prepare_arabic_text_for_pdf(text)
    assert prepared != ""
    assert len(prepared) > 0
