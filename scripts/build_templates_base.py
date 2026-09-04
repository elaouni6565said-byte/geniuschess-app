import os

os.makedirs('templates', exist_ok=True)

html = """{% load static gca_tags %}
<!DOCTYPE html>
<html lang="{{ CURRENT_LANG }}" dir="{{ CURRENT_DIR }}">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{% block title %}{% trans "app_name" %}{% endblock %} — GCA 2026</title>
    <link rel="stylesheet" href="{% static 'css/gca-style.css' %}">
    {% block extra_head %}{% endblock %}
</head>
<body>

    <!-- Official Bilingual Navbar -->
    <header class="gca-navbar">
        <div class="brand-section">
            <div class="brand-logo-badge">♞</div>
            <div class="brand-titles">
                <h1>{% trans "app_name" %}</h1>
                <span>{% trans "app_tagline" %}</span>
            </div>
        </div>

        <nav>
            <ul class="nav-links">
                <li class="nav-item {% if request.resolver_match.url_name == 'dashboard' %}active{% endif %}">
                    <a href="{% url 'portal:dashboard' %}">📊 {% trans "nav.dashboard" %}</a>
                </li>
                <li class="nav-item {% if request.resolver_match.url_name == 'students' %}active{% endif %}">
                    <a href="{% url 'portal:students' %}">🎓 {% trans "nav.students" %}</a>
                </li>
                <li class="nav-item {% if request.resolver_match.url_name == 'planning' %}active{% endif %}">
                    <a href="{% url 'portal:planning' %}">📅 {% trans "nav.planning" %}</a>
                </li>
                <li class="nav-item {% if request.resolver_match.url_name == 'payments' %}active{% endif %}">
                    <a href="{% url 'portal:payments' %}">💳 {% trans "nav.payments" %}</a>
                </li>
                <li class="nav-item {% if request.resolver_match.url_name == 'parent_space' %}active{% endif %}">
                    <a href="{% url 'portal:parent_space' %}">👨‍👩‍👧 {% trans "nav.parent_space" %}</a>
                </li>
            </ul>
        </nav>

        <!-- 47.1 Language Selector Widget -->
        <div class="lang-switcher-widget">
            <a href="{% url 'portal:set_language' 'fr' %}" 
               class="lang-btn {% if CURRENT_LANG == 'fr' %}active{% endif %}" 
               title="Passer en Français">
                <span>🇫🇷</span> <span>Français</span>
            </a>
            <a href="{% url 'portal:set_language' 'ar' %}" 
               class="lang-btn {% if CURRENT_LANG == 'ar' %}active{% endif %}" 
               title="التحويل إلى العربية">
                <span>🇲🇦</span> <span>العربية</span>
            </a>
        </div>
    </header>

    <!-- Main Content Area -->
    <main class="main-wrapper">
        {% if messages %}
            {% for message in messages %}
                <div class="alert-banner alert-{{ message.tags }}">
                    <span>{{ message }}</span>
                </div>
            {% endfor %}
        {% endif %}

        {% block content %}{% endblock %}
    </main>

    <!-- Localized Footer -->
    <footer class="gca-footer">
        <p>© 2026 <b>{% trans "app_name" %}</b> — {% trans "receipt.academy_sub" %} • Sidi Kacem / Rabat, Maroc</p>
        <p style="margin-top: 0.25rem; font-size: 0.75rem;">
            {% if CURRENT_LANG == 'fr' %}
                Langue active : <b>Français (LTR)</b> • Appuyez sur <code>Alt + L</code> pour basculer en Arabe.
            {% else %}
                اللغة المفعلة : <b>العربية (RTL)</b> • اضغط على <code>Alt + L</code> للتحويل إلى الفرنسية.
            {% endif %}
        </p>
    </footer>

    <script src="{% static 'js/gca-bilingual.js' %}"></script>
    {% block extra_scripts %}{% endblock %}
</body>
</html>
"""

with open('templates/base.html', 'w', encoding='utf-8') as f:
    f.write(html)

print('Created templates/base.html')
