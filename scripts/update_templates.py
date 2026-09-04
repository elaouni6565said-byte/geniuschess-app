import os

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
                    <td>{{ inv|trans_field:CURRENT_LANG }}</td>
                    <td>{% money inv.amount_due %}</td>
                    <td>{% money inv.amount_paid %}</td>
                    <td style="color: var(--danger); font-weight: bold;">{% money inv.get_balance %}</td>
                    <td>
                        <span class="badge {% if inv.status == 'partial' %}badge-partial{% else %}badge-unpaid{% endif %}">
                            {% if CURRENT_LANG == 'ar' %}{{ inv.status_label_ar }}{% else %}{{ inv.status_label_fr }}{% endif %}
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
                               target="_blank" class="btn btn-secondary btn-sm" title="Reçu PDF Bilingue">
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
                <span>⚠️ <b>{% trans "parent_space.overdue_warning" %}</b> : {{ inv.student|trans_field:CURRENT_LANG }} — {{ inv|trans_field:CURRENT_LANG }} ({% money inv.get_balance %})</span>
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

with open('templates/portal/payments.html', 'w', encoding='utf-8') as f:
    f.write(payments_html)

with open('templates/portal/parent_space.html', 'w', encoding='utf-8') as f:
    f.write(parent_space_html)

print('Updated payments.html and parent_space.html successfully')
