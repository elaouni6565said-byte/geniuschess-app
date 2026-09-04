import os
import django
import pytest

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gca_config.settings')
django.setup()

@pytest.fixture(autouse=True, scope='function')
def enable_db_access_for_all_tests(db):
    pass

@pytest.fixture(scope='session', autouse=True)
def setup_test_data(django_db_setup, django_db_blocker):
    with django_db_blocker.unblock():
        import importlib
        import scripts.seed_demo_data
        importlib.reload(scripts.seed_demo_data)


