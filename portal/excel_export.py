import io
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

NAVY_FILL = PatternFill(start_color="001B57", end_color="001B57", fill_type="solid")
RED_FILL = PatternFill(start_color="991B1B", end_color="991B1B", fill_type="solid")
GREEN_FILL = PatternFill(start_color="047857", end_color="047857", fill_type="solid")
TOTAL_FILL = PatternFill(start_color="EFF6FF", end_color="EFF6FF", fill_type="solid")
UNPAID_TOTAL_FILL = PatternFill(start_color="FEF2F2", end_color="FEF2F2", fill_type="solid")

HEADER_FONT = Font(name="Segoe UI", size=11, bold=True, color="FFFFFF")
TITLE_FONT = Font(name="Segoe UI", size=14, bold=True, color="001B57")
TITLE_RED_FONT = Font(name="Segoe UI", size=14, bold=True, color="991B1B")
TOTAL_FONT = Font(name="Segoe UI", size=11, bold=True, color="001B57")
TOTAL_RED_FONT = Font(name="Segoe UI", size=11, bold=True, color="991B1B")
DATA_FONT = Font(name="Segoe UI", size=10)
BOLD_DATA_FONT = Font(name="Segoe UI", size=10, bold=True)

BORDER_THIN = Border(
    left=Side(style='thin', color='CBD5E1'),
    right=Side(style='thin', color='CBD5E1'),
    top=Side(style='thin', color='CBD5E1'),
    bottom=Side(style='thin', color='CBD5E1'),
)

BORDER_TOTAL = Border(
    left=Side(style='thin', color='CBD5E1'),
    right=Side(style='thin', color='CBD5E1'),
    top=Side(style='thin', color='CBD5E1'),
    bottom=Side(style='double', color='001B57'),
)


def export_students_to_excel(students_queryset, lang="fr"):
    """
    Generates a comprehensive bilingual Excel workbook (.xlsx) of ALL students.
    Supports French, Arabic (RTL), and Bilingual.
    """
    wb = Workbook()
    ws = wb.active

    if lang == "ar":
        ws.title = "قائمة التلاميذ"
        ws.sheet_view.rightToLeft = True
        align_header = Alignment(horizontal="center", vertical="center", wrap_text=True)
        align_data = Alignment(horizontal="right", vertical="center")
        title_text = "GENIUS CHESS ACADEMY - جمعية الشطرنج القاسمي - لائحة جميع التلاميذ المسجلين 2026"
        headers = [
            "رقم التسجيل", "الاسم بالعربية", "الاسم بالفرنسية", "تاريخ الازدياد",
            "النشاط والمستوى", "المجموعة", "ولي الأمر", "الهاتف", "البريد الإلكتروني", "الحالة"
        ]
    elif lang == "bilingual":
        ws.title = "Élèves - التلاميذ"
        align_header = Alignment(horizontal="center", vertical="center", wrap_text=True)
        align_data = Alignment(horizontal="left", vertical="center")
        title_text = "GENIUS CHESS ACADEMY - جمعية الشطرنج القاسمي - Liste Complète des Élèves / لائحة التلاميذ 2026"
        headers = [
            "Matricule / التسجيل", "Nom (FR)", "الاسم (AR)", "Date Naissance",
            "Activité / النشاط", "Groupe / المجموعة", "Parent / ولي الأمر", "Tél / الهاتف", "Email", "Statut / الحالة"
        ]
    else: # fr
        ws.title = "Liste des Élèves"
        align_header = Alignment(horizontal="center", vertical="center", wrap_text=True)
        align_data = Alignment(horizontal="left", vertical="center")
        title_text = "GENIUS CHESS ACADEMY - جمعية الشطرنج القاسمي - Liste Complète des Élèves Inscrits 2026"
        headers = [
            "Matricule", "Nom (Français)", "Nom (Arabe)", "Date de Naissance",
            "Activité & Niveau", "Groupe", "Parent / Tuteur", "Téléphone", "Email", "Statut"
        ]

    # Title row
    last_col_letter = get_column_letter(len(headers))
    ws.merge_cells(f"A1:{last_col_letter}1")
    title_cell = ws["A1"]
    title_cell.value = title_text
    title_cell.font = TITLE_FONT
    title_cell.alignment = Alignment(horizontal="center", vertical="center")
    ws.row_dimensions[1].height = 35

    # Headers row
    ws.row_dimensions[3].height = 28
    for col_num, header in enumerate(headers, 1):
        cell = ws.cell(row=3, column=col_num)
        cell.value = header
        cell.font = HEADER_FONT
        cell.fill = NAVY_FILL
        cell.alignment = align_header
        cell.border = BORDER_THIN

    # Data rows
    row_idx = 4
    for st in students_queryset:
        ws.row_dimensions[row_idx].height = 22
        group = st.groups.first()
        subject_str = group.subject.get_bilingual_name() if group and group.subject else ("Échecs / الشطرنج" if st.active else "-")
        group_str = group.get_name(lang) if group else "-"
        parent_str = st.parent.get_name(lang) if st.parent else "-"
        phone_str = st.parent.phone if st.parent else "-"
        email_str = st.parent.email if (st.parent and st.parent.email) else "-"
        birth_str = st.birth_date.strftime("%d/%m/%Y") if st.birth_date else "-"
        status_str = "Actif / نشط" if st.active else "Inactif / غير نشط"

        row_values = [
            st.registration_number,
            f"{st.first_name_ar} {st.last_name_ar}".strip(),
            f"{st.first_name_fr} {st.last_name_fr}".strip(),
            birth_str,
            subject_str,
            group_str,
            parent_str,
            phone_str,
            email_str,
            status_str,
        ]
        if lang == "ar":
            row_values[1], row_values[2] = row_values[2], row_values[1]

        for col_num, val in enumerate(row_values, 1):
            cell = ws.cell(row=row_idx, column=col_num)
            cell.value = val
            cell.font = DATA_FONT
            cell.alignment = align_data
            cell.border = BORDER_THIN
        row_idx += 1

    # Auto-adjust column widths
    for col in ws.columns:
        max_len = max(len(str(cell.value or '')) for cell in col)
        col_letter = get_column_letter(col[0].column)
        ws.column_dimensions[col_letter].width = max(max_len + 4, 12)

    buffer = io.BytesIO()
    wb.save(buffer)
    excel_bytes = buffer.getvalue()
    buffer.close()
    return excel_bytes


def export_paid_payments_to_excel(payments_queryset, lang="fr"):
    """
    Generates an official Excel workbook (.xlsx) of all received / paid payments.
    Includes totals row, bilingual support, and formatted amounts.
    """
    wb = Workbook()
    ws = wb.active

    if lang == "ar":
        ws.title = "المقبوضات والأداءات"
        ws.sheet_view.rightToLeft = True
        align_header = Alignment(horizontal="center", vertical="center", wrap_text=True)
        align_data = Alignment(horizontal="right", vertical="center")
        title_text = "GENIUS CHESS ACADEMY - جمعية الشطرنج القاسمي - قائمة المقبوضات والأداءات المؤداة 2026"
        headers = [
            "رقم الإيصال", "تاريخ الأداء", "رقم التسجيل", "اسم التلميذ (بالعربية)", "اسم التلميذ (بالفرنسية)",
            "المادة / النشاط", "المجموعة", "ولي الأمر", "الهاتف", "طريقة الأداء", "المبلغ المؤدى (درهم)"
        ]
    elif lang == "bilingual":
        ws.title = "Paiements Réglés"
        align_header = Alignment(horizontal="center", vertical="center", wrap_text=True)
        align_data = Alignment(horizontal="left", vertical="center")
        title_text = "GENIUS CHESS ACADEMY - جمعية الشطرنج القاسمي - Liste des Paiements Réglés / قائمة المقبوضات 2026"
        headers = [
            "N° Reçu", "Date Paiement", "Matricule", "Élève (FR)", "الاسم (AR)",
            "Activité / النشاط", "Groupe", "Parent / ولي الأمر", "Téléphone", "Mode Règlement", "Montant (DH)"
        ]
    else: # fr
        ws.title = "Liste des Paiements"
        align_header = Alignment(horizontal="center", vertical="center", wrap_text=True)
        align_data = Alignment(horizontal="left", vertical="center")
        title_text = "GENIUS CHESS ACADEMY - جمعية الشطرنج القاسمي - Liste des Paiements Encaissés (Payants) 2026"
        headers = [
            "N° Reçu", "Date Paiement", "Matricule", "Nom Élève (FR)", "Nom Élève (AR)",
            "Activité", "Groupe", "Parent / Tuteur", "Téléphone", "Mode Règlement", "Montant Réglé (DH)"
        ]

    # Title row
    last_col_letter = get_column_letter(len(headers))
    ws.merge_cells(f"A1:{last_col_letter}1")
    title_cell = ws["A1"]
    title_cell.value = title_text
    title_cell.font = TITLE_FONT
    title_cell.alignment = Alignment(horizontal="center", vertical="center")
    ws.row_dimensions[1].height = 35

    # Headers row
    ws.row_dimensions[3].height = 28
    for col_num, header in enumerate(headers, 1):
        cell = ws.cell(row=3, column=col_num)
        cell.value = header
        cell.font = HEADER_FONT
        cell.fill = NAVY_FILL
        cell.alignment = align_header
        cell.border = BORDER_THIN

    # Data rows
    row_idx = 4
    total_amount = 0.0

    for p in payments_queryset:
        ws.row_dimensions[row_idx].height = 22
        st = p.student
        group = p.invoice.group if (p.invoice and p.invoice.group) else (st.groups.first() if st else None)
        subject_str = group.subject.get_name(lang) if (group and group.subject) else "-"
        group_str = group.get_name(lang) if group else "-"
        parent_str = st.parent.get_name(lang) if (st and st.parent) else "-"
        phone_str = st.parent.phone if (st and st.parent) else "-"
        
        # Payment method localized
        method_labels = {
            'cash': 'Espèces / نقداً',
            'bank_transfer': 'Virement bancaire / تحويل بنكي',
            'check': 'Chèque / شيك',
            'online': 'En ligne / أداء إلكتروني',
        }
        method_str = method_labels.get(p.payment_method, p.payment_method or "Espèces")
        amt = float(p.amount)
        total_amount += amt

        row_values = [
            f"#{p.receipt_number}",
            p.payment_date.strftime("%d/%m/%Y"),
            st.registration_number if st else "-",
            f"{st.first_name_fr} {st.last_name_fr}".strip() if st else "-",
            f"{st.first_name_ar} {st.last_name_ar}".strip() if st else "-",
            subject_str,
            group_str,
            parent_str,
            phone_str,
            method_str,
            amt,
        ]
        if lang == "ar":
            row_values[3], row_values[4] = row_values[4], row_values[3]

        for col_num, val in enumerate(row_values, 1):
            cell = ws.cell(row=row_idx, column=col_num)
            cell.value = val
            cell.font = DATA_FONT
            cell.border = BORDER_THIN
            if col_num == len(headers):
                cell.alignment = Alignment(horizontal="right", vertical="center")
                cell.number_format = '#,##0.00 "DH"'
                cell.font = BOLD_DATA_FONT
            else:
                cell.alignment = align_data
        row_idx += 1

    # Total Summary Row
    ws.row_dimensions[row_idx].height = 28
    ws.merge_cells(start_row=row_idx, start_column=1, end_row=row_idx, end_column=len(headers) - 1)
    tot_label = ws.cell(row=row_idx, column=1)
    tot_label.value = "TOTAL DES RECETTES ENCAISSÉES / مجموع المقبوضات :" if lang != "ar" else "مجموع المبالغ المؤداة المحصلة :"
    tot_label.font = TOTAL_FONT
    tot_label.fill = TOTAL_FILL
    tot_label.alignment = Alignment(horizontal="right" if lang != "ar" else "left", vertical="center")
    tot_label.border = BORDER_TOTAL

    tot_val = ws.cell(row=row_idx, column=len(headers))
    tot_val.value = total_amount
    tot_val.font = TOTAL_FONT
    tot_val.fill = TOTAL_FILL
    tot_val.alignment = Alignment(horizontal="right", vertical="center")
    tot_val.number_format = '#,##0.00 "DH"'
    tot_val.border = BORDER_TOTAL

    # Auto-adjust column widths
    for col in ws.columns:
        max_len = max(len(str(cell.value or '')) for cell in col)
        col_letter = get_column_letter(col[0].column)
        ws.column_dimensions[col_letter].width = max(max_len + 4, 12)

    buffer = io.BytesIO()
    wb.save(buffer)
    excel_bytes = buffer.getvalue()
    buffer.close()
    return excel_bytes


def export_unpaid_invoices_to_excel(invoices_queryset, lang="fr"):
    """
    Generates an official Excel workbook (.xlsx) of all unpaid / partially paid students (Impayés).
    Includes contact info for reminders, outstanding balance, and total unpaid amount.
    """
    wb = Workbook()
    ws = wb.active

    if lang == "ar":
        ws.title = "المستحقات غير المؤداة"
        ws.sheet_view.rightToLeft = True
        align_header = Alignment(horizontal="center", vertical="center", wrap_text=True)
        align_data = Alignment(horizontal="right", vertical="center")
        title_text = "GENIUS CHESS ACADEMY - جمعية الشطرنج القاسمي - لائحة المستحقات غير المؤداة (المتأخرات) 2026"
        headers = [
            "رقم التسجيل", "اسم التلميذ (بالعربية)", "اسم التلميذ (بالفرنسية)", "ولي الأمر",
            "رقم الهاتف للمتابعة", "المادة / النشاط", "الشهر المعني", "الواجب الشهري (درهم)",
            "المبلغ المدفوع (درهم)", "الباقي المستحق (درهم)", "الحالة"
        ]
    elif lang == "bilingual":
        ws.title = "Impayés - المتأخرات"
        align_header = Alignment(horizontal="center", vertical="center", wrap_text=True)
        align_data = Alignment(horizontal="left", vertical="center")
        title_text = "GENIUS CHESS ACADEMY - جمعية الشطرنج القاسمي - Liste des Impayés / لائحة المستحقات غير المؤداة 2026"
        headers = [
            "Matricule", "Élève (FR)", "الاسم (AR)", "Parent / ولي الأمر",
            "Tél Relance", "Activité / النشاط", "Mois", "Montant Dû (DH)",
            "Payé (DH)", "Reste Impayé (DH)", "Statut / الحالة"
        ]
    else: # fr
        ws.title = "Liste des Impayés"
        align_header = Alignment(horizontal="center", vertical="center", wrap_text=True)
        align_data = Alignment(horizontal="left", vertical="center")
        title_text = "GENIUS CHESS ACADEMY - جمعية الشطرنج القاسمي - Liste des Élèves Non-Payants & Impayés 2026"
        headers = [
            "Matricule", "Nom Élève (FR)", "Nom Élève (AR)", "Parent / Tuteur",
            "Téléphone Relance", "Activité & Niveau", "Mois Concerné", "Montant Dû (DH)",
            "Déjà Versé (DH)", "Reste Impayé (DH)", "Statut"
        ]

    # Title row
    last_col_letter = get_column_letter(len(headers))
    ws.merge_cells(f"A1:{last_col_letter}1")
    title_cell = ws["A1"]
    title_cell.value = title_text
    title_cell.font = TITLE_RED_FONT
    title_cell.alignment = Alignment(horizontal="center", vertical="center")
    ws.row_dimensions[1].height = 35

    # Headers row
    ws.row_dimensions[3].height = 28
    for col_num, header in enumerate(headers, 1):
        cell = ws.cell(row=3, column=col_num)
        cell.value = header
        cell.font = HEADER_FONT
        cell.fill = RED_FILL
        cell.alignment = align_header
        cell.border = BORDER_THIN

    # Data rows
    row_idx = 4
    total_due = 0.0
    total_paid = 0.0
    total_balance = 0.0

    for inv in invoices_queryset:
        ws.row_dimensions[row_idx].height = 22
        st = inv.student
        group = inv.group if inv.group else (st.groups.first() if st else None)
        subject_str = group.subject.get_name(lang) if (group and group.subject) else "-"
        parent_str = st.parent.get_name(lang) if (st and st.parent) else "-"
        phone_str = st.parent.phone if (st and st.parent) else "-"
        month_str = inv.get_period_label(lang)

        amt_due = float(inv.amount_due)
        amt_paid = float(inv.amount_paid)
        balance = float(inv.get_balance())

        total_due += amt_due
        total_paid += amt_paid
        total_balance += balance

        status_str = "Impayé / غير مؤدى" if inv.status == 'unpaid' else "Partiel / أداء جزئي"

        row_values = [
            st.registration_number if st else "-",
            f"{st.first_name_fr} {st.last_name_fr}".strip() if st else "-",
            f"{st.first_name_ar} {st.last_name_ar}".strip() if st else "-",
            parent_str,
            phone_str,
            subject_str,
            month_str,
            amt_due,
            amt_paid,
            balance,
            status_str,
        ]
        if lang == "ar":
            row_values[1], row_values[2] = row_values[2], row_values[1]

        for col_num, val in enumerate(row_values, 1):
            cell = ws.cell(row=row_idx, column=col_num)
            cell.value = val
            cell.font = DATA_FONT
            cell.border = BORDER_THIN
            if col_num in (8, 9):
                cell.alignment = Alignment(horizontal="right", vertical="center")
                cell.number_format = '#,##0.00 "DH"'
            elif col_num == 10:
                cell.alignment = Alignment(horizontal="right", vertical="center")
                cell.number_format = '#,##0.00 "DH"'
                cell.font = Font(name="Segoe UI", size=10, bold=True, color="991B1B")
            else:
                cell.alignment = align_data
        row_idx += 1

    # Total Summary Row
    ws.row_dimensions[row_idx].height = 28
    ws.merge_cells(start_row=row_idx, start_column=1, end_row=row_idx, end_column=7)
    tot_label = ws.cell(row=row_idx, column=1)
    tot_label.value = "TOTAL DES IMPAYÉS RESTANTS / مجموع المتأخرات المتبقية :" if lang != "ar" else "مجموع المتأخرات المتبقية المستحقة :"
    tot_label.font = TOTAL_RED_FONT
    tot_label.fill = UNPAID_TOTAL_FILL
    tot_label.alignment = Alignment(horizontal="right" if lang != "ar" else "left", vertical="center")
    tot_label.border = BORDER_TOTAL

    tot_due_cell = ws.cell(row=row_idx, column=8)
    tot_due_cell.value = total_due
    tot_due_cell.font = BOLD_DATA_FONT
    tot_due_cell.fill = UNPAID_TOTAL_FILL
    tot_due_cell.alignment = Alignment(horizontal="right", vertical="center")
    tot_due_cell.number_format = '#,##0.00 "DH"'
    tot_due_cell.border = BORDER_TOTAL

    tot_paid_cell = ws.cell(row=row_idx, column=9)
    tot_paid_cell.value = total_paid
    tot_paid_cell.font = BOLD_DATA_FONT
    tot_paid_cell.fill = UNPAID_TOTAL_FILL
    tot_paid_cell.alignment = Alignment(horizontal="right", vertical="center")
    tot_paid_cell.number_format = '#,##0.00 "DH"'
    tot_paid_cell.border = BORDER_TOTAL

    tot_bal_cell = ws.cell(row=row_idx, column=10)
    tot_bal_cell.value = total_balance
    tot_bal_cell.font = TOTAL_RED_FONT
    tot_bal_cell.fill = UNPAID_TOTAL_FILL
    tot_bal_cell.alignment = Alignment(horizontal="right", vertical="center")
    tot_bal_cell.number_format = '#,##0.00 "DH"'
    tot_bal_cell.border = BORDER_TOTAL

    ws.cell(row=row_idx, column=11).border = BORDER_TOTAL
    ws.cell(row=row_idx, column=11).fill = UNPAID_TOTAL_FILL

    # Auto-adjust column widths
    for col in ws.columns:
        max_len = max(len(str(cell.value or '')) for cell in col)
        col_letter = get_column_letter(col[0].column)
        ws.column_dimensions[col_letter].width = max(max_len + 4, 12)

    buffer = io.BytesIO()
    wb.save(buffer)
    excel_bytes = buffer.getvalue()
    buffer.close()
    return excel_bytes


def export_expenses_to_excel(expenses_queryset, lang="fr", month=None, year=None):
    """
    Génère un classeur Excel officiel (.xlsx) du registre des dépenses et charges.
    Prend en charge le français, l'arabe (RTL) et le bilingue, avec ligne de totalisation.
    """
    wb = Workbook()
    ws = wb.active

    period_str = ""
    if month and year:
        period_str = f" - {month:02d}/{year}"
    elif year:
        period_str = f" - Année {year}"

    if lang == "ar":
        ws.title = "سجل المصاريف"
        ws.sheet_view.rightToLeft = True
        align_header = Alignment(horizontal="center", vertical="center", wrap_text=True)
        align_data = Alignment(horizontal="right", vertical="center")
        title_text = f"GENIUS CHESS ACADEMY - جمعية الشطرنج القاسمي - سجل المصاريف والنفقات{period_str}"
        headers = [
            "التاريخ", "بيان المصروف", "الصنف / الفئة", "المستفيد / الجهة",
            "رقم الفاتورة / الوصل", "طريقة الأداء", "المبلغ (درهم)", "ملاحظات"
        ]
    elif lang == "bilingual":
        ws.title = "Dépenses - المصاريف"
        align_header = Alignment(horizontal="center", vertical="center", wrap_text=True)
        align_data = Alignment(horizontal="left", vertical="center")
        title_text = f"GENIUS CHESS ACADEMY - جمعية الشطرنج القاسمي - Registre des Dépenses{period_str}"
        headers = [
            "Date / التاريخ", "Libellé / البيان", "Catégorie / الصنف", "Bénéficiaire / المستفيد",
            "N° Facture / الوصل", "Mode Règlement", "Montant / المبلغ (DH)", "Remarques / ملاحظات"
        ]
    else: # fr
        ws.title = "Dépenses"
        align_header = Alignment(horizontal="center", vertical="center", wrap_text=True)
        align_data = Alignment(horizontal="left", vertical="center")
        title_text = f"GENIUS CHESS ACADEMY - جمعية الشطرنج القاسمي - Registre des Dépenses et Charges{period_str}"
        headers = [
            "Date", "Libellé de la Dépense", "Catégorie", "Bénéficiaire / Fournisseur",
            "N° Facture / Réf", "Mode de Règlement", "Montant (DH)", "Observations"
        ]

    # Title row
    last_col_letter = get_column_letter(len(headers))
    ws.merge_cells(f"A1:{last_col_letter}1")
    title_cell = ws["A1"]
    title_cell.value = title_text
    title_cell.font = TITLE_FONT
    title_cell.alignment = Alignment(horizontal="center", vertical="center")
    ws.row_dimensions[1].height = 35

    # Subtitle / Coordinates row
    ws.merge_cells(f"A2:{last_col_letter}2")
    sub_cell = ws["A2"]
    sub_cell.value = "Sidi Kacem • www.geniuschess.ma • Tél: 06 060424142"
    sub_cell.font = Font(name="Segoe UI", size=9, italic=True, color="64748B")
    sub_cell.alignment = Alignment(horizontal="center", vertical="center")
    ws.row_dimensions[2].height = 18

    # Headers row
    ws.row_dimensions[4].height = 28
    for col_num, header in enumerate(headers, 1):
        cell = ws.cell(row=4, column=col_num)
        cell.value = header
        cell.font = HEADER_FONT
        cell.fill = NAVY_FILL
        cell.alignment = align_header
        cell.border = BORDER_THIN

    # Data rows
    row_idx = 5
    total_amount = 0.0

    for exp in expenses_queryset:
        ws.row_dimensions[row_idx].height = 22
        cat_name = exp.category.get_name(lang) if exp.category else "-"
        date_str = exp.expense_date.strftime("%d/%m/%Y") if exp.expense_date else "-"
        method_str = exp.get_method_label(lang)
        amt = float(exp.amount)
        total_amount += amt

        row_values = [
            date_str,
            exp.title,
            cat_name,
            exp.beneficiary or "-",
            exp.invoice_number or "-",
            method_str,
            amt,
            exp.notes or "-",
        ]

        for col_num, val in enumerate(row_values, 1):
            cell = ws.cell(row=row_idx, column=col_num)
            cell.value = val
            cell.font = DATA_FONT
            cell.border = BORDER_THIN
            if col_num == 7:
                cell.alignment = Alignment(horizontal="right", vertical="center")
                cell.number_format = '#,##0.00 "DH"'
                cell.font = BOLD_DATA_FONT
            elif col_num == 1:
                cell.alignment = Alignment(horizontal="center", vertical="center")
            else:
                cell.alignment = align_data
        row_idx += 1

    # Total Summary Row
    ws.row_dimensions[row_idx].height = 28
    ws.merge_cells(start_row=row_idx, start_column=1, end_row=row_idx, end_column=6)
    tot_label = ws.cell(row=row_idx, column=1)
    tot_label.value = "TOTAL GÉNÉRAL DES DÉPENSES / مجموع المصاريف :" if lang != "ar" else "مجموع المصاريف الإجمالي :"
    tot_label.font = TOTAL_FONT
    tot_label.fill = TOTAL_FILL
    tot_label.alignment = Alignment(horizontal="right" if lang != "ar" else "left", vertical="center")
    tot_label.border = BORDER_TOTAL

    tot_cell = ws.cell(row=row_idx, column=7)
    tot_cell.value = total_amount
    tot_cell.font = TOTAL_FONT
    tot_cell.fill = TOTAL_FILL
    tot_cell.alignment = Alignment(horizontal="right", vertical="center")
    tot_cell.number_format = '#,##0.00 "DH"'
    tot_cell.border = BORDER_TOTAL

    notes_total_cell = ws.cell(row=row_idx, column=8)
    notes_total_cell.border = BORDER_TOTAL
    notes_total_cell.fill = TOTAL_FILL

    # Auto-adjust column widths
    for col in ws.columns:
        max_len = max(len(str(cell.value or '')) for cell in col)
        col_letter = get_column_letter(col[0].column)
        ws.column_dimensions[col_letter].width = max(max_len + 4, 13)

    buffer = io.BytesIO()
    wb.save(buffer)
    excel_bytes = buffer.getvalue()
    buffer.close()
    return excel_bytes

