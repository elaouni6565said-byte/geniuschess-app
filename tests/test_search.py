import pytest
from core.i18n import normalize_text_for_search

def test_bilingual_unicode_search_normalization():
    """Tests accent-insensitive and Arabic variation normalization (47.13 & 47.14)."""
    # French accents
    assert normalize_text_for_search("Élève") == "eleve"
    assert normalize_text_for_search("Août") == "aout"

    # Arabic variants
    assert normalize_text_for_search("أحمد") == normalize_text_for_search("احمد")
    assert normalize_text_for_search("إدريسي") == normalize_text_for_search("ادريسي")
    assert normalize_text_for_search("فاطمة") == normalize_text_for_search("فاطمه")
    assert normalize_text_for_search("سارة") == normalize_text_for_search("ساره")
    assert normalize_text_for_search("يوسف") == normalize_text_for_search("ىوسف")
