import os

os.makedirs('templates/portal', exist_ok=True)

# 1. Dashboard Template
dashboard_html = """{% extends "base.html" %}
{% load gca_tags %}

{% block title %}{% trans "dashboard.title" %} — {% trans "app_name" %}{% endblock %}

{% block content %}
<div class="page-header">
    <div class="page-header-titles">
        <h2>{% trans "dashboard.title" %}</h2>
        <p>{% trans "dashboard.subtitle" %}</p>
    </div>
    <div class="page-actions">
        <a href="{% url 'portal:run_reminders' %}" class="btn btn-accent" title="{% trans 'dashboard.run_reminders_btn' %}">
            🔔 {% trans "dashboard.run_reminders_btn" %}
        </a>
    </div>
</div>

<!-- KPI Cards -->
<div class="grid-kpi">
    <div class="kpi-card">
        <div class="kpi-content">
            <h4>{% trans "dashboard.total_students" %}</h4>
            <div class="kpi-value">{{ total_students }}</div>
        </div>
        <div class="kpi-icon blue">🎓</div>
    </div>

    <div class="kpi-card">
        <div class="kpi-content">
            <h4>{% trans "dashboard.active_groups" %}</h4>
            <div class="kpi-value">{{ active_groups }}</div>
        </div>
        <div class="kpi-icon navy">👥</div>
    </div>

    <div class="kpi-card">
        <div class="kpi-content">
            <h4>{% trans "dashboard.monthly_revenue" %}</h4>
            <div class="kpi-value" style="color: var(--success);">{% money total_revenue %}</div>
        </div>
        <div class="kpi-icon green">💰</div>
    </div>

    <div class="kpi-card">
        <div class="kpi-content">
            <h4>{% trans "dashboard.unpaid_total" %}</h4>
            <div class="kpi-value" style="color: var(--danger);">{% money total_unpaid %}</div>
        </div>
        <div class="kpi-icon red">⚠️</div>
    </div>
</div>

<!-- Main Sections Grid -->
<div style="display: grid; grid-template-columns: 2fr 1fr; gap: 1.5rem;">
    <!-- Recent Payments Card -->
    <div class="card">
        <div class="card-header">
            <h3 class="card-title">💳 {% trans "dashboard.recent_payments" %}</h3>
            <a href="{% url 'portal:payments' %}" class="btn btn-outline btn-sm">
                {% trans "common.all" %} <span class="icon-dir">→</span>
            </a>
        </div>
        <div class="table-responsive">
            <table class="gca-table">
                <thead>
                    <tr>
                        <th>{% trans "payments.receipt_no" %}</th>
                        <th>{% trans "payments.student" %}</th>
                        <th>{% trans "payments.amount" %}</th>
                        <th>{% trans "payments.payment_date" %}</th>
                        <th>{% trans "payments.method" %}</th>
                        <th>PDF</th>
                    </tr>
                </thead>
                <tbody>
                    {% for p in recent_payments %}
                    <tr>
                        <td><b>#{{ p.receipt_number }}</b></td>
                        <td>{{ p.student|trans_field:CURRENT_LANG }}</td>
                        <td style="font-weight: bold; color: var(--primary-blue);">{% money p.amount %}</td>
                        <td>{% local_date p.payment_date %}</td>
                        <td>{{ p|trans_field:CURRENT_LANG }}</td>
                        <td>
                            <a href="{% url 'portal:receipt_pdf' p.id %}?lang={{ CURRENT_LANG }}" 
                               target="_blank" class="btn btn-outline btn-sm" title="Télécharger">
                                📄 PDF
                            </a>
                        </td>
                    </tr>
                    {% empty %}
                    <tr>
                        <td colspan="6" style="text-align: center; color: var(--text-muted); padding: 2rem;">
                            {% trans "common.not_found" %}
                        </td>
                    </tr>
                    {% endfor %}
                </tbody>
            </table>
        </div>
    </div>

    <!-- Quick Actions & Dynamic Activities -->
    <div>
        <div class="card">
            <div class="card-header">
                <h3 class="card-title">⚡ {% trans "dashboard.quick_actions" %}</h3>
            </div>
            <div style="display: flex; flex-direction: column; gap: 0.75rem;">
                <a href="{% url 'portal:students' %}" class="btn btn-secondary">
                    🎓 {% trans "students.title" %}
                </a>
                <a href="{% url 'portal:planning' %}" class="btn btn-outline">
                    📅 {% trans "planning.title" %}
                </a>
                <a href="{% url 'portal:payments' %}" class="btn btn-outline">
                    💳 {% trans "payments.title" %}
                </a>
                <a href="{% url 'portal:export_students_excel' %}" class="btn btn-outline">
                    📥 {% trans "students.export_excel" %}
                </a>
            </div>
        </div>

        <div class="card">
            <div class="card-header">
                <h3 class="card-title">♟️ {% trans "dashboard.activities_distribution" %}</h3>
            </div>
            <ul style="list-style: none; display: flex; flex-direction: column; gap: 0.75rem;">
                {% for act in activities %}
                <li style="display: flex; justify-content: space-between; align-items: center; padding: 0.5rem 0.75rem; background: #F8FAFC; border-radius: var(--radius-sm); border-right: 4px solid {{ act.color }}; border-left: 4px solid {{ act.color }};">
                    <span style="font-weight: 600;">{{ act|trans_field:CURRENT_LANG }}</span>
                    <span class="badge" style="background: {{ act.color }}; color: white;">
                        {{ act.groups.count }} {% trans "nav.planning" %}
                    </span>
                </li>
                {% endfor %}
            </ul>
        </div>
    </div>
</div>
{% endblock %}
"""

# 2. Students Template
students_html = """{% extends "base.html" %}
{% load gca_tags %}

{% block title %}{% trans "students.title" %} — {% trans "app_name" %}{% endblock %}

{% block content %}
<div class="page-header">
    <div class="page-header-titles">
        <h2>{% trans "students.title" %}</h2>
        <p>{% trans "students.subtitle" %}</p>
    </div>
    <div class="page-actions">
        <a href="{% url 'portal:export_students_excel' %}" class="btn btn-secondary">
            📥 {% trans "students.export_excel" %}
        </a>
    </div>
</div>

<!-- Bilingual Search & Filter Bar (47.13) -->
<form method="GET" action="{% url 'portal:students' %}" class="filter-bar">
    <div class="search-input-wrapper">
        <input type="text" name="q" value="{{ query }}" class="search-input"
               placeholder="{% trans 'students.search_placeholder' %}">
    </div>

    <select name="activity" class="filter-select">
        <option value="">{% trans "students.all_activities" %}</option>
        {% for act in activities %}
            <option value="{{ act.id }}" {% if selected_activity == act.id %}selected{% endif %}>
                {{ act|trans_field:CURRENT_LANG }}
            </option>
        {% endfor %}
    </select>

    <button type="submit" class="btn btn-primary">
        🔍 {% trans "students.filter_btn" %}
    </button>
    {% if query or selected_activity %}
        <a href="{% url 'portal:students' %}" class="btn btn-outline">
            ✕ {% trans "students.reset_btn" %}
        </a>
    {% endif %}
</form>

<!-- Students Table -->
<div class="card">
    <div class="table-responsive">
        <table class="gca-table">
            <thead>
                <tr>
                    <th>Matricule</th>
                    <th>{% trans "students.name_fr" %}</th>
                    <th>{% trans "students.name_ar" %}</th>
                    <th>{% trans "students.activity" %}</th>
                    <th>{% trans "students.parent" %}</th>
                    <th>{% trans "students.phone" %}</th>
                    <th>{% trans "students.status" %}</th>
                </tr>
            </thead>
            <tbody>
                {% for st in students %}
                <tr>
                    <td><b>{{ st.registration_number }}</b></td>
                    <td>{{ st.first_name_fr }} {{ st.last_name_fr }}</td>
                    <td style="font-weight: 600; color: var(--primary-navy);">{{ st.first_name_ar }} {{ st.last_name_ar }}</td>
                    <td>
                        {% for g in st.groups.all %}
                            <span class="badge" style="background: #E2E8F0; color: #1E293B;">
                                {{ g.subject|trans_field:CURRENT_LANG }}
                            </span>
                        {% empty %}
                            <span style="color: var(--text-muted);">-</span>
                        {% endfor %}
                    </td>
                    <td>{{ st.parent|trans_field:CURRENT_LANG }}</td>
                    <td><bdi>{{ st.parent.phone }}</bdi></td>
                    <td>
                        {% if st.active %}
                            <span class="badge badge-paid">✓ {% trans "common.success" %}</span>
                        {% else %}
                            <span class="badge badge-unpaid">✕</span>
                        {% endif %}
                    </td>
                </tr>
                {% empty %}
                <tr>
                    <td colspan="7" style="text-align: center; color: var(--text-muted); padding: 3rem;">
                        <p style="font-size: 1.1rem; margin-bottom: 0.5rem;">🔍 {% trans "students.no_students_found" %}</p>
                        <p style="font-size: 0.85rem;">Essayez avec un autre mot-clé (ex: <i>Mohamed</i> ou <i>محمد</i>).</p>
                    </td>
                </tr>
                {% endfor %}
            </tbody>
        </table>
    </div>
</div>
{% endblock %}
"""

# 3. Planning Template
planning_html = """{% extends "base.html" %}
{% load gca_tags %}

{% block title %}{% trans "planning.title" %} — {% trans "app_name" %}{% endblock %}

{% block content %}
<div class="page-header">
    <div class="page-header-titles">
        <h2>{% trans "planning.title" %}</h2>
        <p>{% trans "planning.subtitle" %}</p>
    </div>
</div>

<!-- Weekly Schedule localized (47.8) -->
<div style="display: flex; flex-direction: column; gap: 1.5rem;">
    {% for day in days_data %}
    <div class="card" style="margin-bottom: 0.5rem;">
        <div class="card-header" style="background: #F8FAFC; padding: 0.75rem 1rem; border-radius: var(--radius-sm);">
            <h3 class="card-title" style="font-size: 1.1rem; color: var(--primary-navy);">
                🗓️ {{ day.day_name }}
            </h3>
            <span class="badge" style="background: var(--primary-blue); color: white;">
                {{ day.sessions|length }} {% trans "planning.students_count" %}
            </span>
        </div>
        
        {% if day.sessions %}
        <div style="display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 1rem; margin-top: 1rem;">
            {% for s in day.sessions %}
            <div style="border: 1px solid var(--border-color); border-radius: var(--radius-sm); padding: 1rem; background: white; border-inline-start: 4px solid {{ s.group.subject.color }};">
                <div style="display: flex; justify-content: space-between; margin-bottom: 0.5rem;">
                    <b style="color: var(--primary-navy);">{{ s.group.subject|trans_field:CURRENT_LANG }}</b>
                    <span style="font-weight: 700; color: var(--accent-orange); font-size: 0.85rem;">
                        <bdi>{{ s.start_time|time:"H:i" }} - {{ s.end_time|time:"H:i" }}</bdi>
                    </span>
                </div>
                <p style="font-size: 0.9rem; color: var(--text-main); margin-bottom: 0.25rem;">
                    👥 {{ s.group|trans_field:CURRENT_LANG }}
                </p>
                <p style="font-size: 0.85rem; color: var(--text-muted); margin-bottom: 0.25rem;">
                    📍 {{ s.room|trans_field:CURRENT_LANG }}
                </p>
                <p style="font-size: 0.85rem; color: var(--primary-blue);">
                    👨‍🏫 {{ s|trans_field:CURRENT_LANG }}
                </p>
            </div>
            {% endfor %}
        </div>
        {% else %}
            <p style="color: var(--text-muted); padding: 0.75rem 0.5rem; font-size: 0.85rem;">
                {% trans "planning.no_sessions" %}
            </p>
        {% endif %}
    </div>
    {% endfor %}
</div>
{% endblock %}
"""

# 4. Payments Template
payments_html = """{% extends "base.html" %}
{% load gca_tags %}

{% block title %}{% trans "payments.title" %} — {% trans "app_name" %}{% endblock %}

{% block content %}
<div class="page-header">
    <div class="page-header-titles">
        <h2>{% trans "payments.title" %}</h2>
        <p>{% trans "payments.subtitle" %}</p>
    </div>
</div>

<!-- Unpaid Dues Notice / Impayés (47.7 & 47.11) -->
{% if unpaid_invoices %}
<div class="card" style="border-inline-start: 4px solid var(--danger);">
    <div class="card-header">
        <h3 class="card-title" style="color: var(--danger);">
            ⚠️ {% trans "nav.unpaid" %} ({{ unpaid_invoices.count }})
        </h3>
        <a href="{% url 'portal:run_reminders' %}" class="btn btn-accent btn-sm">
            🔔 {% trans "dashboard.run_reminders_btn" %}
        </a>
    </div>
    <div class="table-responsive">
        <table class="gca-table">
            <thead>
                <tr>
                    <th>{% trans "payments.student" %}</th>
                    <th>{% trans "payments.month_paid" %}</th>
                    <th>{% trans "payments.amount_due" %}</th>
                    <th>{% trans "payments.amount_paid" %}</th>
                    <th>{% trans "payments.balance" %}</th>
                    <th>{% trans "payments.status" %}</th>
                </tr>
            </thead>
            <tbody>
                {% for inv in unpaid_invoices %}
                <tr>
                    <td><b>{{ inv.student|trans_field:CURRENT_LANG }}</b></td>
                    <td>{{ inv.get_period_label:CURRENT_LANG }}</td>
                    <td>{% money inv.amount_due %}</td>
                    <td>{% money inv.amount_paid %}</td>
                    <td style="color: var(--danger); font-weight: bold;">{% money inv.get_balance %}</td>
                    <td>
                        <span class="badge {% if inv.status == 'partial' %}badge-partial{% else %}badge-unpaid{% endif %}">
                            {{ inv.get_status_label:CURRENT_LANG }}
                        </span>
                    </td>
                </tr>
                {% endfor %}
            </tbody>
        </table>
    </div>
</div>
{% endif %}

<!-- Payments History & Multi-Lingual PDF Generator (47.7) -->
<div class="card">
    <div class="card-header">
        <h3 class="card-title">🧾 {% trans "nav.receipts" %}</h3>
    </div>
    <div class="table-responsive">
        <table class="gca-table">
            <thead>
                <tr>
                    <th>{% trans "payments.receipt_no" %}</th>
                    <th>{% trans "payments.student" %}</th>
                    <th>{% trans "payments.amount" %}</th>
                    <th>{% trans "payments.payment_date" %}</th>
                    <th>{% trans "payments.method" %}</th>
                    <th style="text-align: center;">Générer Reçu PDF (Spéc. 47.7)</th>
                </tr>
            </thead>
            <tbody>
                {% for p in payments %}
                <tr>
                    <td><b>#{{ p.receipt_number }}</b></td>
                    <td>{{ p.student|trans_field:CURRENT_LANG }}</td>
                    <td style="font-weight: bold; color: var(--primary-blue);">{% money p.amount %}</td>
                    <td>{% local_date p.payment_date %}</td>
                    <td>{{ p|trans_field:CURRENT_LANG }}</td>
                    <td style="text-align: center;">
                        <div style="display: inline-flex; gap: 0.35rem;">
                            <!-- PDF Français -->
                            <a href="{% url 'portal:receipt_pdf' p.id %}?lang=fr" 
                               target="_blank" class="btn btn-outline btn-sm" title="Reçu PDF en Français">
                                🇫🇷 FR
                            </a>
                            <!-- PDF Arabe RTL -->
                            <a href="{% url 'portal:receipt_pdf' p.id %}?lang=ar" 
                               target="_blank" class="btn btn-outline btn-sm" title="وصل أداء بالعربية مع RTL">
                                🇲🇦 AR
                            </a>
                            <!-- PDF Bilingue -->
                            <a href="{% url 'portal:receipt_pdf' p.id %}?lang=bilingual" 
                               target="_blank" class="btn btn-secondary btn-sm" title="Reçu PDF Bilingue côte à côte">
                                🌐 Bilingue
                            </a>
                        </div>
                    </td>
                </tr>
                {% empty %}
                <tr>
                    <td colspan="6" style="text-align: center; color: var(--text-muted); padding: 2rem;">
                        {% trans "common.not_found" %}
                    </td>
                </tr>
                {% endfor %}
            </tbody>
        </table>
    </div>
</div>
{% endblock %}
"""

# 5. Parent Space Template (47.9)
parent_space_html = """{% extends "base.html" %}
{% load gca_tags %}

{% block title %}{% trans "parent_space.title" %} — {% trans "app_name" %}{% endblock %}

{% block content %}
<div class="page-header">
    <div class="page-header-titles">
        <h2>👨‍👩‍👧 {% trans "parent_space.title" %}</h2>
        <p>{% trans "parent_space.welcome" %} : <b>{{ parent|trans_field:CURRENT_LANG }}</b></p>
    </div>
    <div class="page-actions">
        <!-- Direct Language Toggle from Parent Account (47.9) -->
        <span style="font-size: 0.85rem; color: var(--text-muted);">{% trans "switch_language" %} :</span>
        <a href="{% url 'portal:set_language' 'fr' %}" class="btn btn-outline btn-sm {% if CURRENT_LANG == 'fr' %}active{% endif %}">🇫🇷 FR</a>
        <a href="{% url 'portal:set_language' 'ar' %}" class="btn btn-outline btn-sm {% if CURRENT_LANG == 'ar' %}active{% endif %}">🇲🇦 AR</a>
    </div>
</div>

<!-- Overdue Alert if any -->
{% if invoices %}
    {% for inv in invoices %}
        {% if inv.is_overdue %}
            <div class="alert-banner alert-warning">
                <span>⚠️ <b>{% trans "parent_space.overdue_warning" %}</b> : {{ inv.student|trans_field:CURRENT_LANG }} — {{ inv.get_period_label:CURRENT_LANG }} ({% money inv.get_balance %})</span>
            </div>
        {% endif %}
    {% endfor %}
{% endif %}

<!-- Children List (Mes enfants / أبنائي) -->
<div class="card">
    <div class="card-header">
        <h3 class="card-title">👶 {% trans "parent_space.my_children" %} ({{ children|length }})</h3>
    </div>
    <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(320px, 1fr)); gap: 1.25rem;">
        {% for ch in children %}
        <div style="border: 1.5px solid var(--border-color); border-radius: var(--radius-md); padding: 1.25rem; background: #FAFAFA;">
            <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 0.75rem;">
                <div>
                    <h4 style="font-size: 1.15rem; color: var(--primary-navy);">{{ ch|trans_field:CURRENT_LANG }}</h4>
                    <span style="font-size: 0.8rem; color: var(--text-muted);">Matricule: {{ ch.registration_number }}</span>
                </div>
                <span class="badge badge-paid">Inscrit / مسجل</span>
            </div>

            <p style="font-size: 0.85rem; font-weight: 600; color: var(--primary-blue); margin-bottom: 0.5rem;">
                🎯 {% trans "parent_space.enrolled_activities" %} :
            </p>
            <ul style="list-style: none; display: flex; flex-direction: column; gap: 0.35rem; margin-bottom: 1rem;">
                {% for g in ch.groups.all %}
                <li style="font-size: 0.85rem; background: white; padding: 0.35rem 0.65rem; border-radius: var(--radius-sm); border: 1px solid var(--border-color);">
                    <b>{{ g.subject|trans_field:CURRENT_LANG }}</b> ({{ g|trans_field:CURRENT_LANG }})
                </li>
                {% endfor %}
            </ul>
        </div>
        {% empty %}
        <p style="color: var(--text-muted); padding: 1rem;">{% trans "common.not_found" %}</p>
        {% endfor %}
    </div>
</div>

<!-- Payments & Receipts Table for Parent -->
<div class="card">
    <div class="card-header">
        <h3 class="card-title">🧾 {% trans "parent_space.payments_history" %}</h3>
    </div>
    <div class="table-responsive">
        <table class="gca-table">
            <thead>
                <tr>
                    <th>{% trans "payments.receipt_no" %}</th>
                    <th>{% trans "parent_space.child_name" %}</th>
                    <th>{% trans "payments.amount" %}</th>
                    <th>{% trans "payments.payment_date" %}</th>
                    <th>{% trans "parent_space.download_receipt" %}</th>
                </tr>
            </thead>
            <tbody>
                {% for pay in payments %}
                <tr>
                    <td><b>#{{ pay.receipt_number }}</b></td>
                    <td>{{ pay.student|trans_field:CURRENT_LANG }}</td>
                    <td style="color: var(--success); font-weight: bold;">{% money pay.amount %}</td>
                    <td>{% local_date pay.payment_date %}</td>
                    <td>
                        <div style="display: inline-flex; gap: 0.35rem;">
                            <a href="{% url 'portal:receipt_pdf' pay.id %}?lang={{ CURRENT_LANG }}" 
                               target="_blank" class="btn btn-primary btn-sm">
                                📥 {% trans "parent_space.download_receipt" %} ({{ CURRENT_LANG|upper }})
                            </a>
                            <a href="{% url 'portal:receipt_pdf' pay.id %}?lang=bilingual" 
                               target="_blank" class="btn btn-outline btn-sm">
                                🌐 Bilingue
                            </a>
                        </div>
                    </td>
                </tr>
                {% empty %}
                <tr>
                    <td colspan="5" style="text-align: center; color: var(--text-muted); padding: 1.5rem;">
                        {% trans "common.not_found" %}
                    </td>
                </tr>
                {% endfor %}
            </tbody>
        </table>
    </div>
</div>

<!-- Notifications Center (47.10) -->
<div class="card">
    <div class="card-header">
        <h3 class="card-title">🔔 {% trans "parent_space.notifications_center" %}</h3>
    </div>
    <div style="display: flex; flex-direction: column; gap: 0.75rem;">
        {% for n in notifications %}
        <div style="padding: 0.85rem 1rem; border-radius: var(--radius-sm); background: #F8FAFC; border-inline-start: 4px solid var(--primary-blue);">
            <div style="display: flex; justify-content: space-between; margin-bottom: 0.25rem;">
                <b style="color: var(--primary-navy);">{{ n|trans_field:CURRENT_LANG }}</b>
                <span style="font-size: 0.75rem; color: var(--text-muted);">{% local_date n.created_at include_time=True %}</span>
            </div>
            <p style="font-size: 0.9rem; color: var(--text-main);">
                {% if CURRENT_LANG == 'ar' %}{{ n.message_ar }}{% else %}{{ n.message_fr }}{% endif %}
            </p>
        </div>
        {% empty %}
        <p style="color: var(--text-muted); padding: 1rem;">{% trans "common.not_found" %}</p>
        {% endfor %}
    </div>
</div>
{% endblock %}
"""

with open('templates/portal/dashboard.html', 'w', encoding='utf-8') as f:
    f.write(dashboard_html)

with open('templates/portal/students.html', 'w', encoding='utf-8') as f:
    f.write(students_html)

with open('templates/portal/planning.html', 'w', encoding='utf-8') as f:
    f.write(planning_html)

with open('templates/portal/payments.html', 'w', encoding='utf-8') as f:
    f.write(payments_html)

with open('templates/portal/parent_space.html', 'w', encoding='utf-8') as f:
    f.write(parent_space_html)

print('Created all portal templates successfully!')
