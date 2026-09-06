import os
import json
import pytest
from django.test import Client
from django.conf import settings

@pytest.mark.django_db
def test_pwa_manifest_endpoint():
    client = Client()
    resp = client.get('/manifest.webmanifest')
    assert resp.status_code == 200
    assert 'application/manifest+json' in resp.headers.get('Content-Type')
    
    data = json.loads(resp.content.decode('utf-8'))
    assert 'Genius Chess Academy' in data['name']
    assert data['display'] == 'standalone'
    assert data['start_url'] == '/'
    assert len(data['icons']) >= 2

@pytest.mark.django_db
def test_pwa_service_worker_endpoint():
    client = Client()
    resp = client.get('/service-worker.js')
    assert resp.status_code == 200
    assert 'application/javascript' in resp.headers.get('Content-Type')
    assert resp.headers.get('Service-Worker-Allowed') == '/'
    content = resp.content.decode('utf-8')
    assert 'gca-pwa-v1' in content

@pytest.mark.django_db
def test_pwa_icons_exist():
    base_dir = settings.BASE_DIR
    icons = [
        'static/img/icons/icon-192.png',
        'static/img/icons/icon-512.png',
        'static/img/icons/icon-maskable-192.png',
        'static/img/icons/icon-maskable-512.png',
        'static/img/icons/apple-touch-icon.png',
    ]
    for rel_path in icons:
        full_path = os.path.join(base_dir, rel_path)
        assert os.path.exists(full_path), f'Missing icon: {rel_path}'
        assert os.path.getsize(full_path) > 1000

@pytest.mark.django_db
def test_base_html_pwa_meta():
    client = Client()
    resp = client.get('/login/')
    html = resp.content.decode('utf-8')
    assert 'manifest.webmanifest' in html
    assert 'apple-touch-icon' in html
    assert 'theme-color' in html
    assert 'gcaPwaInstallBtn' in html