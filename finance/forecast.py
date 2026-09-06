from decimal import Decimal
from datetime import date, datetime
from django.db.models import Sum, Count, Q
from academy.models import Student, Group, Subject
from finance.models import Invoice, Payment, Expense, ExpenseCategory
from core.i18n import FRENCH_MONTHS, ARABIC_MONTHS, format_currency


def get_monthly_financial_forecast(month=None, year=None, lang="fr"):
    """
    Calcule le bilan et les indicateurs previsionnels financiers pour le mois/annee specifie.
    Mesure precisement le taux de recouvrement a l'echeance du 15 du mois.
    """
    today = date.today()
    if not month:
        month = today.month
    if not year:
        year = today.year

    month = int(month)
    year = int(year)

    # 1. Factures du mois selectionne
    invoices = Invoice.objects.filter(
        period_month=month,
        period_year=year
    ).select_related("student", "student__parent", "group", "group__subject")

    total_expected = invoices.aggregate(total=Sum("amount_due"))["total"] or Decimal("0.00")
    total_invoiced_count = invoices.count()

    paid_invoices_count = invoices.filter(status="paid").count()
    partial_invoices_count = invoices.filter(status="partial").count()
    unpaid_invoices_count = invoices.filter(status="unpaid").count()

    # 2. Total encaisse sur les factures de ce mois
    total_collected = invoices.aggregate(total=Sum("amount_paid"))["total"] or Decimal("0.00")
    total_remaining = max(Decimal("0.00"), total_expected - total_collected)

    recovery_rate = 0.0
    if total_expected > Decimal("0.00"):
        recovery_rate = round(float((total_collected / total_expected) * 100), 1)

    # 3. Barometre de l'Echeance du 15 du mois
    payments_for_month = Payment.objects.filter(invoice__in=invoices)

    collected_before_15 = Decimal("0.00")
    collected_after_15 = Decimal("0.00")

    for p in payments_for_month:
        if p.payment_date <= date(year, month, 15):
            collected_before_15 += p.amount
        else:
            collected_after_15 += p.amount

    rate_at_15 = 0.0
    if total_expected > Decimal("0.00"):
        rate_at_15 = round(float((collected_before_15 / total_expected) * 100), 1)

    # Statut temporel de l'echeance du 15
    deadline_date = date(year, month, 15)
    days_left = (deadline_date - today).days

    if year == today.year and month == today.month:
        if days_left > 0:
            deadline_status = "pending"
            deadline_badge_fr = f"J-{days_left} avant l'echeance du 15"
            deadline_badge_ar = f"بقي {days_left} ايام على اجل 15 من الشهر"
        elif days_left == 0:
            deadline_status = "today"
            deadline_badge_fr = "Aujourd'hui : Jour J de l'echeance (15)"
            deadline_badge_ar = "اليوم هو اخر اجل محدد (15 من الشهر)"
        else:
            deadline_status = "passed"
            overdue_days = abs(days_left)
            deadline_badge_fr = f"Echeance du 15 depassee (il y a {overdue_days} j.) — Relances recommandees"
            deadline_badge_ar = f"انقضى اجل 15 من الشهر (منذ {overdue_days} يوم) — ينصح بالارسال"
    elif (year < today.year) or (year == today.year and month < today.month):
        deadline_status = "past_month"
        deadline_badge_fr = "Mois cloture — Historique d'encaissement"
        deadline_badge_ar = "شهر ماض — ارشيف الاستخلاص"
    else:
        deadline_status = "future_month"
        deadline_badge_fr = "Mois previsionnel futur"
        deadline_badge_ar = "شهر مستقبلي متوقع"

    # 4. Ventilation par Activite (Subject)
    subjects = Subject.objects.all().prefetch_related("groups")
    activities_data = []

    for sub in subjects:
        sub_invoices = invoices.filter(group__subject=sub)
        sub_expected = sub_invoices.aggregate(total=Sum("amount_due"))["total"] or Decimal("0.00")
        sub_collected = sub_invoices.aggregate(total=Sum("amount_paid"))["total"] or Decimal("0.00")
        sub_remaining = max(Decimal("0.00"), sub_expected - sub_collected)
        sub_rate = round(float((sub_collected / sub_expected) * 100), 1) if sub_expected > Decimal("0.00") else 0.0

        groups_data = []
        for grp in sub.groups.all():
            grp_invs = sub_invoices.filter(group=grp)
            grp_expected = grp_invs.aggregate(total=Sum("amount_due"))["total"] or Decimal("0.00")
            grp_collected = grp_invs.aggregate(total=Sum("amount_paid"))["total"] or Decimal("0.00")
            grp_rem = max(Decimal("0.00"), grp_expected - grp_collected)
            grp_rate = round(float((grp_collected / grp_expected) * 100), 1) if grp_expected > Decimal("0.00") else 0.0

            if grp_invs.exists() or grp.students.filter(active=True).exists():
                groups_data.append({
                    "group": grp,
                    "name_fr": grp.name_fr,
                    "name_ar": grp.name_ar,
                    "color": grp.get_color(),
                    "students_count": grp.students.filter(active=True).count(),
                    "expected": grp_expected,
                    "collected": grp_collected,
                    "remaining": grp_rem,
                    "rate": grp_rate,
                    "unpaid_count": grp_invs.filter(status__in=["unpaid", "partial"]).count()
                })

        if sub_expected > Decimal("0.00") or len(groups_data) > 0:
            activities_data.append({
                "subject": sub,
                "name_fr": sub.name_fr,
                "name_ar": sub.name_ar,
                "color": sub.color,
                "expected": sub_expected,
                "collected": sub_collected,
                "remaining": sub_remaining,
                "rate": sub_rate,
                "groups": groups_data
            })

    # 5. Dépenses & Charges du mois sélectionné
    expenses_qs = Expense.objects.filter(expense_date__year=year, expense_date__month=month)
    total_expenses = expenses_qs.aggregate(total=Sum("amount"))["total"] or Decimal("0.00")
    expenses_count = expenses_qs.count()
    net_result = total_collected - total_expenses

    categories_breakdown = []
    for cat in ExpenseCategory.objects.filter(is_active=True):
        cat_amount = expenses_qs.filter(category=cat).aggregate(total=Sum("amount"))["total"] or Decimal("0.00")
        if cat_amount > Decimal("0.00"):
            cat_pct = round(float((cat_amount / total_expenses) * 100), 1) if total_expenses > Decimal("0.00") else 0.0
            categories_breakdown.append({
                "category": cat,
                "name": cat.get_name(lang),
                "name_fr": cat.name_fr,
                "name_ar": cat.name_ar,
                "icon": cat.icon,
                "color": cat.color,
                "amount": cat_amount,
                "percentage": cat_pct,
            })
    categories_breakdown.sort(key=lambda x: x["amount"], reverse=True)

    # 6. Historique des 6 derniers mois (Recettes vs Dépenses vs Résultat Net)
    history = []
    curr_y = year
    curr_m = month
    for _ in range(6):
        m_label_fr = FRENCH_MONTHS.get(curr_m, str(curr_m)).capitalize()[:4]
        m_label_ar = ARABIC_MONTHS.get(curr_m, str(curr_m))
        h_invs = Invoice.objects.filter(period_month=curr_m, period_year=curr_y)
        h_exp = h_invs.aggregate(total=Sum("amount_due"))["total"] or Decimal("0.00")
        h_col = h_invs.aggregate(total=Sum("amount_paid"))["total"] or Decimal("0.00")
        h_rate = round(float((h_col / h_exp) * 100), 1) if h_exp > Decimal("0.00") else 0.0

        h_expenses_qs = Expense.objects.filter(expense_date__year=curr_y, expense_date__month=curr_m)
        h_expenses = h_expenses_qs.aggregate(total=Sum("amount"))["total"] or Decimal("0.00")
        h_net = h_col - h_expenses

        history.append({
            "month": curr_m,
            "year": curr_y,
            "label_fr": f"{m_label_fr} {curr_y}",
            "label_ar": f"{m_label_ar} {curr_y}",
            "expected": h_exp,
            "collected": h_col,
            "expenses": h_expenses,
            "net_result": h_net,
            "rate": h_rate,
            "is_current": (curr_m == month and curr_y == year)
        })

        curr_m -= 1
        if curr_m == 0:
            curr_m = 12
            curr_y -= 1

    history.reverse()

    period_label_fr = f"{FRENCH_MONTHS.get(month, str(month)).capitalize()} {year}"
    period_label_ar = f"{ARABIC_MONTHS.get(month, str(month))} {year}"

    return {
        "selected_month": month,
        "selected_year": year,
        "period_label_fr": period_label_fr,
        "period_label_ar": period_label_ar,
        "period_label": period_label_ar if lang == "ar" else period_label_fr,
        "total_expected": total_expected,
        "total_collected": total_collected,
        "total_remaining": total_remaining,
        "total_expenses": total_expenses,
        "net_result": net_result,
        "expenses_count": expenses_count,
        "categories_breakdown": categories_breakdown,
        "recovery_rate": recovery_rate,
        "total_invoiced_count": total_invoiced_count,
        "paid_invoices_count": paid_invoices_count,
        "partial_invoices_count": partial_invoices_count,
        "unpaid_invoices_count": unpaid_invoices_count,
        "collected_before_15": collected_before_15,
        "collected_after_15": collected_after_15,
        "rate_at_15": rate_at_15,
        "deadline_status": deadline_status,
        "deadline_badge_fr": deadline_badge_fr,
        "deadline_badge_ar": deadline_badge_ar,
        "deadline_badge": deadline_badge_ar if lang == "ar" else deadline_badge_fr,
        "activities_data": activities_data,
        "history": history,
        "months_list": [{"num": m, "name_fr": FRENCH_MONTHS[m].capitalize(), "name_ar": ARABIC_MONTHS[m]} for m in range(1, 13)],
        "years_list": [2025, 2026, 2027],
    }
