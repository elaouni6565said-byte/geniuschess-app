import io
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter
from portal.excel_validator import (
    deduplicate_items,
    sanitize_header_list,
    align_row_to_headers,
    audit_and_correct_worksheet,
)

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


def get_student_activities_and_count(student, invoice=None, lang="fr"):
    """
    Retourne : (activities_str, nb_activities, groups_str)
    - activities_str : toutes les activités distinctes suivies par l'élève, séparées par ' + ' (ex: 'Échecs + Robotique')
    - nb_activities : nombre total d'activités distinctes suivies (ex: 2)
    - groups_str : tous les groupes auxquels l'élève est inscrit (ex: 'Groupe A + Groupe B')
    """
    if not student:
        return "-", 1, "-"

    # Collecter tous les groupes associés à l'élève
    groups = []
    if hasattr(student, 'groups'):
        groups = list(student.groups.all())

    # Si aucun groupe directement rattaché à l'élève mais qu'une facture en spécifie un
    if not groups and invoice and getattr(invoice, 'group', None):
        groups = [invoice.group]

    subjects = []
    seen_sub_ids = set()
    for g in groups:
        if g and g.subject and g.subject.id not in seen_sub_ids:
            seen_sub_ids.add(g.subject.id)
            if lang == "ar":
                subjects.append(g.subject.get_name("ar"))
            elif lang == "bilingual":
                subjects.append(g.subject.get_bilingual_name())
            else:
                subjects.append(g.subject.get_name("fr"))

    if not subjects:
        if invoice and getattr(invoice, 'group', None) and invoice.group.subject:
            s = invoice.group.subject
            if lang == "ar":
                subjects.append(s.get_name("ar"))
            elif lang == "bilingual":
                subjects.append(s.get_bilingual_name())
            else:
                subjects.append(s.get_name("fr"))
        elif getattr(student, 'active', True):
            default_sub = "Échecs" if lang != "ar" else "شطرنج"
            if lang == "bilingual":
                default_sub = "Échecs / الشطرنج"
            subjects = [default_sub]

    nb_activities = max(1, len(subjects)) if subjects else 1
    plus_sep = " + "
    activities_str = plus_sep.join(subjects) if subjects else "-"

    group_names = [g.get_name(lang) for g in groups if g]
    group_names = list(dict.fromkeys(group_names))
    groups_str = plus_sep.join(group_names) if group_names else "-"

    return activities_str, nb_activities, groups_str


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
            "الأنشطة المستفاد منها", "عدد الأنشطة", "المجموعة / المجموعات", "ولي الأمر", "الهاتف", "البريد الإلكتروني", "الحالة"
        ]
    elif lang == "bilingual":
        ws.title = "Élèves - التلاميذ"
        align_header = Alignment(horizontal="center", vertical="center", wrap_text=True)
        align_data = Alignment(horizontal="left", vertical="center")
        title_text = "GENIUS CHESS ACADEMY - جمعية الشطرنج القاسمي - Liste Complète des Élèves / لائحة التلاميذ 2026"
        headers = [
            "Matricule / التسجيل", "Nom (FR)", "الاسم (AR)", "Date Naissance",
            "Activités / الأنشطة", "Nb Activités / عدد الأنشطة", "Groupe(s) / المجموعات", "Parent / ولي الأمر", "Tél / الهاتف", "Email", "Statut / الحالة"
        ]
    else: # fr
        ws.title = "Liste des Élèves"
        align_header = Alignment(horizontal="center", vertical="center", wrap_text=True)
        align_data = Alignment(horizontal="left", vertical="center")
        title_text = "GENIUS CHESS ACADEMY - جمعية الشطرنج القاسمي - Liste Complète des Élèves Inscrits 2026"
        headers = [
            "Matricule", "Nom (Français)", "Nom (Arabe)", "Date de Naissance",
            "Activités Suivies", "Nombre d'activités", "Groupe(s)", "Parent / Tuteur", "Téléphone", "Email", "Statut"
        ]

    # Sanitize and deduplicate headers
    headers, kept_cols = sanitize_header_list(headers)

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

    # Data rows (Deduplicated sources)
    students_list = deduplicate_items(students_queryset, key_func=lambda s: getattr(s, 'id', s))
    row_idx = 4
    for st in students_list:
        ws.row_dimensions[row_idx].height = 22
        activities_str, nb_activities, group_str = get_student_activities_and_count(st, lang=lang)
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
            activities_str,
            nb_activities,
            group_str,
            parent_str,
            phone_str,
            email_str,
            status_str,
        ]
        if lang == "ar":
            row_values[1], row_values[2] = row_values[2], row_values[1]

        # Ensure strict alignment with headers
        row_values = align_row_to_headers(row_values, len(headers), kept_cols)

        for col_num, val in enumerate(row_values, 1):
            cell = ws.cell(row=row_idx, column=col_num)
            cell.value = val
            cell.font = DATA_FONT
            cell.border = BORDER_THIN
            if col_num == 6:
                cell.alignment = Alignment(horizontal="center", vertical="center")
                cell.font = BOLD_DATA_FONT
            else:
                cell.alignment = align_data
        row_idx += 1

    # Système de vérification et correction automatique de la feuille (lignes et colonnes)
    audit_and_correct_worksheet(ws, candidate_header_row=3)

    buffer = io.BytesIO()
    wb.save(buffer)
    excel_bytes = buffer.getvalue()
    buffer.close()
    return excel_bytes


def compute_centre_and_trainer_share(amount, nb_activities):
    """
    Règle officielle de répartition des recettes pour Genius Chess Academy :
    - Pour chaque activité de chaque élève, le centre reçoit 35 DH (1 activité = 35 DH, 2 activités = 70 DH).
    - Le reste revient au coach / formateur (Montant total - Part du centre).
    """
    amt = float(amount or 0.0)
    nb = max(1, int(nb_activities or 1))

    part_centre = min(amt, 35.0 * nb)
    part_prof = max(0.0, amt - part_centre)
    return part_centre, part_prof


def export_paid_payments_to_excel(payments_queryset, unpaid_invoices_queryset=None, lang="fr"):
    """
    Génère l'état officiel consolidé des encaissements (.xlsx) selon la maquette exacte GCA 2026 :
    1. Tableau des Payants (Encaissés) avec les 11 colonnes réglementaires :
       N° Reçu, Date, Matricule, Nom FR, Nom AR, Activités, Motif Réduction, Montant, Nb Activités, Part Centre, Part Prof
    2. Totaux des recettes encaissées avec répartition Centre et Professeurs.
    3. Tableau des Non-Payants & Impayés en bas avec le même niveau de détail et calculs prévisionnels.
    4. Récapitulatif consolidé général (Chiffre d'affaires global et taux de recouvrement).
    """
    wb = Workbook()
    ws = wb.active

    if lang == "ar":
        ws.title = "المقبوضات والمتأخرات"
        ws.sheet_view.rightToLeft = True
        align_header = Alignment(horizontal="center", vertical="center", wrap_text=True)
        align_data = Alignment(horizontal="right", vertical="center")
        title_text = "GENIUS CHESS ACADEMY - جمعية الشطرنج القاسمي - قائمة المقبوضات والأداءات المؤداة 2026"
        headers_paid = [
            "رقم الإيصال", "تاريخ الأداء", "الشهر المؤدى عنه", "رقم التسجيل", "اسم التلميذ (بالفرنسية)", "اسم التلميذ (بالعربية)",
            "الأنشطة المستفاد منها", "الاتفاقية / سبب التخفيض", "المبلغ المؤدى (درهم)", "عدد الأنشطة", "حصة المركز", "حصة الأستاذ"
        ]
        headers_unpaid = [
            "رقم الفاتورة", "تاريخ الاستحقاق", "الشهر المستحق (المعني)", "رقم التسجيل", "اسم التلميذ (بالفرنسية)", "اسم التلميذ (بالعربية)",
            "الأنشطة المستفاد منها", "الاتفاقية / سبب التخفيض", "المبلغ المستحق (درهم)", "عدد الأنشطة", "حصة المركز المتوقعة", "حصة الأستاذ المتوقعة"
        ]
    elif lang == "bilingual":
        ws.title = "Paiements & Impayés"
        align_header = Alignment(horizontal="center", vertical="center", wrap_text=True)
        align_data = Alignment(horizontal="left", vertical="center")
        title_text = "GENIUS CHESS ACADEMY - جمعية الشطرنج القاسمي - Liste des Paiements Encaissés (Payants) 2026"
        headers_paid = [
            "N° Reçu", "Date Paiement", "Mois Concerné / الشهر المؤدى عنه", "Matricule", "Nom Élève (FR)", "Nom Élève (AR)",
            "Activités Bénéficiées", "Motif de Réduction / Convention", "Montant Réglé (DH)", "Nombre d'activitées", "Part du centre", "Part du prof"
        ]
        headers_unpaid = [
            "N° Facture", "Date Échéance", "Mois Concerné / الشهر المستحق", "Matricule", "Nom Élève (FR)", "Nom Élève (AR)",
            "Activités Bénéficiées", "Motif de Réduction / Convention", "Montant Dû (DH)", "Nombre d'activitées", "Part du centre", "Part du prof"
        ]
    else: # fr
        ws.title = "Liste des Paiements"
        align_header = Alignment(horizontal="center", vertical="center", wrap_text=True)
        align_data = Alignment(horizontal="left", vertical="center")
        title_text = "GENIUS CHESS ACADEMY - جمعية الشطرنج القاسمي - Liste des Paiements Encaissés (Payants) 2026"
        headers_paid = [
            "N° Reçu", "Date Paiement", "Mois Concerné (Période)", "Matricule", "Nom Élève (FR)", "Nom Élève (AR)",
            "Activités Bénéficiées", "Motif de Réduction / Convention", "Montant Réglé (DH)", "Nombre d'activitées", "Part du centre", "Part du prof"
        ]
        headers_unpaid = [
            "N° Facture", "Date Échéance", "Mois Concerné (Période)", "Matricule", "Nom Élève (FR)", "Nom Élève (AR)",
            "Activités Bénéficiées", "Motif de Réduction / Convention", "Montant Dû (DH)", "Nombre d'activitées", "Part du centre", "Part du prof"
        ]

    # Sanitize and deduplicate headers
    headers_paid, kept_paid = sanitize_header_list(headers_paid)
    headers_unpaid, kept_unpaid = sanitize_header_list(headers_unpaid)

    # Title row
    last_col_letter = get_column_letter(len(headers_paid))
    ws.merge_cells(f"A1:{last_col_letter}1")
    title_cell = ws["A1"]
    title_cell.value = title_text
    title_cell.font = TITLE_FONT
    title_cell.alignment = Alignment(horizontal="center", vertical="center")
    ws.row_dimensions[1].height = 35

    # Headers row
    ws.row_dimensions[3].height = 28
    for col_num, header in enumerate(headers_paid, 1):
        cell = ws.cell(row=3, column=col_num)
        cell.value = header
        cell.font = HEADER_FONT
        cell.fill = NAVY_FILL
        cell.alignment = align_header
        cell.border = BORDER_THIN

    # 1. SECTION PAYANTS (Deduplicated)
    payments_list = deduplicate_items(payments_queryset, key_func=lambda p: getattr(p, 'id', p))
    row_idx = 4
    total_amount = 0.0
    total_centre = 0.0
    total_prof = 0.0

    for p in payments_list:
        ws.row_dimensions[row_idx].height = 22
        st = p.student
        
        # Récupération de toutes les activités suivies et de leur nombre
        activities_str, nb_activities, _ = get_student_activities_and_count(st, invoice=p.invoice, lang=lang)
        
        # Motif de réduction le cas échéant
        reduction_str = "-"
        if st:
            inv = p.invoice
            discount_val = 0.0
            if inv and inv.discount_amount > 0:
                discount_val = float(inv.discount_amount)
            elif st.has_convention:
                _, disc, _ = st.calculate_monthly_fee()
                discount_val = float(disc)

            if st.has_convention and st.convention_name:
                if discount_val > 0:
                    reduction_str = f"{st.convention_name} (-{discount_val:.2f} DH)" if lang != "ar" else f"{st.convention_name} (تخفيض {discount_val:.2f} درهم)"
                else:
                    reduction_str = st.convention_name
            elif discount_val > 0:
                reduction_str = f"Réduction (-{discount_val:.2f} DH)" if lang != "ar" else f"تخفيض ({discount_val:.2f} درهم)"

        amt = float(p.amount)
        part_centre, part_prof = compute_centre_and_trainer_share(amt, nb_activities)

        total_amount += amt
        total_centre += part_centre
        total_prof += part_prof

        period_name = p.get_period_label(lang)
        if p.is_deferred:
            period_name += " (Différé)" if lang != "ar" else " (مؤجل)"

        row_values = [
            f"#{p.receipt_number}",
            p.payment_date.strftime("%d/%m/%Y"),
            period_name,
            st.registration_number if st else "-",
            f"{st.first_name_fr} {st.last_name_fr}".strip() if st else "-",
            f"{st.first_name_ar} {st.last_name_ar}".strip() if st else "-",
            activities_str,
            reduction_str,
            amt,
            nb_activities,
            part_centre,
            part_prof,
        ]

        # Ensure strict alignment with headers
        row_values = align_row_to_headers(row_values, len(headers_paid), kept_paid)

        for col_num, val in enumerate(row_values, 1):
            cell = ws.cell(row=row_idx, column=col_num)
            cell.value = val
            cell.font = DATA_FONT
            cell.border = BORDER_THIN
            if col_num in (9, 11, 12):
                cell.alignment = Alignment(horizontal="right", vertical="center")
                cell.number_format = '#,##0.00 "DH"'
                cell.font = BOLD_DATA_FONT
            elif col_num == 10:
                cell.alignment = Alignment(horizontal="center", vertical="center")
            else:
                cell.alignment = align_data
        row_idx += 1

    # Total Payants Row
    ws.row_dimensions[row_idx].height = 28
    ws.merge_cells(start_row=row_idx, start_column=1, end_row=row_idx, end_column=8)
    for c in range(1, 9):
        ws.cell(row=row_idx, column=c).border = BORDER_TOTAL
        ws.cell(row=row_idx, column=c).fill = TOTAL_FILL

    tot_label = ws.cell(row=row_idx, column=1)
    tot_label.value = "TOTAL DES RECETTES ENCAISSÉES / مجموع المقبوضات :" if lang != "ar" else "مجموع المبالغ المؤداة المحصلة :"
    tot_label.font = TOTAL_FONT
    tot_label.alignment = Alignment(horizontal="right" if lang != "ar" else "left", vertical="center")

    # Montant total réglé
    tot_val = ws.cell(row=row_idx, column=9)
    tot_val.value = total_amount
    tot_val.font = TOTAL_FONT
    tot_val.fill = TOTAL_FILL
    tot_val.alignment = Alignment(horizontal="right", vertical="center")
    tot_val.number_format = '#,##0.00 "DH"'
    tot_val.border = BORDER_TOTAL

    # Col 10 (nb_activités totalisé ou vide)
    c10 = ws.cell(row=row_idx, column=10)
    c10.fill = TOTAL_FILL
    c10.border = BORDER_TOTAL

    # Total Part Centre
    tot_c = ws.cell(row=row_idx, column=11)
    tot_c.value = total_centre
    tot_c.font = TOTAL_FONT
    tot_c.fill = TOTAL_FILL
    tot_c.alignment = Alignment(horizontal="right", vertical="center")
    tot_c.number_format = '#,##0.00 "DH"'
    tot_c.border = BORDER_TOTAL

    # Total Part Prof
    tot_p = ws.cell(row=row_idx, column=12)
    tot_p.value = total_prof
    tot_p.font = TOTAL_FONT
    tot_p.fill = TOTAL_FILL
    tot_p.alignment = Alignment(horizontal="right", vertical="center")
    tot_p.number_format = '#,##0.00 "DH"'
    tot_p.border = BORDER_TOTAL

    row_idx += 1

    # 2. SECTION NON-PAYANTS & IMPAYÉS
    total_unpaid_amount = 0.0
    total_unpaid_centre = 0.0
    total_unpaid_prof = 0.0

    if unpaid_invoices_queryset and unpaid_invoices_queryset.exists():
        # Ligne d'espacement
        ws.row_dimensions[row_idx].height = 20
        row_idx += 1

        # Titre de la section des non-payants
        ws.merge_cells(start_row=row_idx, start_column=1, end_row=row_idx, end_column=len(headers_unpaid))
        unpaid_title_cell = ws.cell(row=row_idx, column=1)
        unpaid_title_cell.value = (
            "⚠️ ÉLÈVES NON PAYANTS & IMPAYÉS (EN ATTENTE DE RÈGLEMENT) / لائحة غير المؤدين والمتأخرات"
            if lang != "ar" else "⚠️ لائحة غير المؤدين والمستحقات المتبقية (المتأخرات)"
        )
        unpaid_title_cell.font = Font(name="Segoe UI", size=12, bold=True, color="FFFFFF")
        unpaid_title_cell.fill = RED_FILL
        unpaid_title_cell.alignment = Alignment(horizontal="center", vertical="center")
        ws.row_dimensions[row_idx].height = 32
        row_idx += 1

        # En-têtes de la section des non-payants
        ws.row_dimensions[row_idx].height = 28
        for col_num, header in enumerate(headers_unpaid, 1):
            cell = ws.cell(row=row_idx, column=col_num)
            cell.value = header
            cell.font = HEADER_FONT
            cell.fill = RED_FILL
            cell.alignment = align_header
            cell.border = BORDER_THIN
        row_idx += 1

        unpaid_list = deduplicate_items(unpaid_invoices_queryset, key_func=lambda inv: getattr(inv, 'id', inv))
        for inv in unpaid_list:
            ws.row_dimensions[row_idx].height = 22
            st = inv.student
            
            # Récupération de toutes les activités suivies et de leur nombre
            activities_str, nb_activities, _ = get_student_activities_and_count(st, invoice=inv, lang=lang)

            # Motif de réduction le cas échéant
            reduction_str = "-"
            if st:
                discount_val = float(inv.discount_amount) if inv.discount_amount > 0 else 0.0
                if discount_val == 0.0 and st.has_convention:
                    _, disc, _ = st.calculate_monthly_fee()
                    discount_val = float(disc)

                if st.has_convention and st.convention_name:
                    if discount_val > 0:
                        reduction_str = f"{st.convention_name} (-{discount_val:.2f} DH)" if lang != "ar" else f"{st.convention_name} (تخفيض {discount_val:.2f} درهم)"
                    else:
                        reduction_str = st.convention_name
                elif discount_val > 0:
                    reduction_str = f"Réduction (-{discount_val:.2f} DH)" if lang != "ar" else f"تخفيض ({discount_val:.2f} درهم)"

            balance = float(inv.get_balance())
            part_centre, part_prof = compute_centre_and_trainer_share(balance, nb_activities)

            total_unpaid_amount += balance
            total_unpaid_centre += part_centre
            total_unpaid_prof += part_prof

            due_date_str = inv.due_date.strftime("%d/%m/%Y") if inv.due_date else f"15/{inv.period_month:02d}/{inv.period_year}"

            period_name = inv.get_period_label(lang)

            row_values = [
                f"#FACT-{inv.id:04d}",
                due_date_str,
                period_name,
                st.registration_number if st else "-",
                f"{st.first_name_fr} {st.last_name_fr}".strip() if st else "-",
                f"{st.first_name_ar} {st.last_name_ar}".strip() if st else "-",
                activities_str,
                reduction_str,
                balance,
                nb_activities,
                part_centre,
                part_prof,
            ]

            # Ensure strict alignment with headers
            row_values = align_row_to_headers(row_values, len(headers_unpaid), kept_unpaid)

            for col_num, val in enumerate(row_values, 1):
                cell = ws.cell(row=row_idx, column=col_num)
                cell.value = val
                cell.font = DATA_FONT
                cell.border = BORDER_THIN
                if col_num in (9, 11, 12):
                    cell.alignment = Alignment(horizontal="right", vertical="center")
                    cell.number_format = '#,##0.00 "DH"'
                    if col_num == 9:
                        cell.font = Font(name="Segoe UI", size=10, bold=True, color="991B1B")
                    else:
                        cell.font = BOLD_DATA_FONT
                elif col_num == 10:
                    cell.alignment = Alignment(horizontal="center", vertical="center")
                else:
                    cell.alignment = align_data
            row_idx += 1

        # Ligne de Total des Impayés
        ws.row_dimensions[row_idx].height = 28
        ws.merge_cells(start_row=row_idx, start_column=1, end_row=row_idx, end_column=8)
        for c in range(1, 9):
            ws.cell(row=row_idx, column=c).border = BORDER_TOTAL
            ws.cell(row=row_idx, column=c).fill = UNPAID_TOTAL_FILL

        tot_unpaid_label = ws.cell(row=row_idx, column=1)
        tot_unpaid_label.value = "TOTAL DES IMPAYÉS RESTANTS / مجموع المتأخرات المتبقية :" if lang != "ar" else "مجموع المتأخرات المتبقية المستحقة :"
        tot_unpaid_label.font = TOTAL_RED_FONT
        tot_unpaid_label.alignment = Alignment(horizontal="right" if lang != "ar" else "left", vertical="center")

        # Montant total impayé
        tot_u_val = ws.cell(row=row_idx, column=9)
        tot_u_val.value = total_unpaid_amount
        tot_u_val.font = TOTAL_RED_FONT
        tot_u_val.fill = UNPAID_TOTAL_FILL
        tot_u_val.alignment = Alignment(horizontal="right", vertical="center")
        tot_u_val.number_format = '#,##0.00 "DH"'
        tot_u_val.border = BORDER_TOTAL

        # Col 10
        c10_u = ws.cell(row=row_idx, column=10)
        c10_u.fill = UNPAID_TOTAL_FILL
        c10_u.border = BORDER_TOTAL

        # Part Centre Impayée
        tot_uc = ws.cell(row=row_idx, column=11)
        tot_uc.value = total_unpaid_centre
        tot_uc.font = BOLD_DATA_FONT
        tot_uc.fill = UNPAID_TOTAL_FILL
        tot_uc.alignment = Alignment(horizontal="right", vertical="center")
        tot_uc.number_format = '#,##0.00 "DH"'
        tot_uc.border = BORDER_TOTAL

        # Part Prof Impayée
        tot_up = ws.cell(row=row_idx, column=12)
        tot_up.value = total_unpaid_prof
        tot_up.font = BOLD_DATA_FONT
        tot_up.fill = UNPAID_TOTAL_FILL
        tot_up.alignment = Alignment(horizontal="right", vertical="center")
        tot_up.number_format = '#,##0.00 "DH"'
        tot_up.border = BORDER_TOTAL

        row_idx += 1

        # 3. SECTION RÉCAPITULATIF CONSOLIDÉ GÉNÉRAL (ENCAISSÉ + IMPAYÉ)
        ws.row_dimensions[row_idx].height = 20
        row_idx += 1

        grand_total_amount = total_amount + total_unpaid_amount
        grand_total_centre = total_centre + total_unpaid_centre
        grand_total_prof = total_prof + total_unpaid_prof
        recovery_rate = (total_amount / grand_total_amount * 100.0) if grand_total_amount > 0 else 100.0

        # Titre Récapitulatif Général
        ws.merge_cells(start_row=row_idx, start_column=1, end_row=row_idx, end_column=len(headers_paid))
        recap_title = ws.cell(row=row_idx, column=1)
        recap_title.value = (
            f"📊 BILAN GLOBAL & CHIFFRE D'AFFAIRES PRÉVISIONNEL (Taux d'encaissement : {recovery_rate:.1f}%)"
            if lang != "ar" else f"📊 الحصيلة المالية الشاملة ومجموع المداخيل المتوقعة (نسبة الاستخلاص : {recovery_rate:.1f}%)"
        )
        recap_title.font = Font(name="Segoe UI", size=12, bold=True, color="FFFFFF")
        recap_title.fill = GREEN_FILL
        recap_title.alignment = Alignment(horizontal="center", vertical="center")
        ws.row_dimensions[row_idx].height = 32
        row_idx += 1

        # Ligne Total Général
        ws.row_dimensions[row_idx].height = 30
        ws.merge_cells(start_row=row_idx, start_column=1, end_row=row_idx, end_column=8)
        for c in range(1, 9):
            ws.cell(row=row_idx, column=c).border = BORDER_TOTAL
            ws.cell(row=row_idx, column=c).fill = PatternFill(start_color="ECFDF5", end_color="ECFDF5", fill_type="solid")

        grand_label = ws.cell(row=row_idx, column=1)
        grand_label.value = "TOTAL GÉNÉRAL PRÉVISIONNEL (ENCAISSÉ + IMPAYÉ) / المجموع العام الإجمالي :" if lang != "ar" else "المجموع العام الإجمالي للمداخيل (المحصلة + المتبقية) :"
        grand_label.font = Font(name="Segoe UI", size=11, bold=True, color="047857")
        grand_label.alignment = Alignment(horizontal="right" if lang != "ar" else "left", vertical="center")

        gt_val = ws.cell(row=row_idx, column=9)
        gt_val.value = grand_total_amount
        gt_val.font = Font(name="Segoe UI", size=11, bold=True, color="047857")
        gt_val.fill = PatternFill(start_color="ECFDF5", end_color="ECFDF5", fill_type="solid")
        gt_val.alignment = Alignment(horizontal="right", vertical="center")
        gt_val.number_format = '#,##0.00 "DH"'
        gt_val.border = BORDER_TOTAL

        gt_c10 = ws.cell(row=row_idx, column=10)
        gt_c10.fill = PatternFill(start_color="ECFDF5", end_color="ECFDF5", fill_type="solid")
        gt_c10.border = BORDER_TOTAL

        gt_centre = ws.cell(row=row_idx, column=11)
        gt_centre.value = grand_total_centre
        gt_centre.font = Font(name="Segoe UI", size=11, bold=True, color="047857")
        gt_centre.fill = PatternFill(start_color="ECFDF5", end_color="ECFDF5", fill_type="solid")
        gt_centre.alignment = Alignment(horizontal="right", vertical="center")
        gt_centre.number_format = '#,##0.00 "DH"'
        gt_centre.border = BORDER_TOTAL

        gt_prof = ws.cell(row=row_idx, column=12)
        gt_prof.value = grand_total_prof
        gt_prof.font = Font(name="Segoe UI", size=11, bold=True, color="047857")
        gt_prof.fill = PatternFill(start_color="ECFDF5", end_color="ECFDF5", fill_type="solid")
        gt_prof.alignment = Alignment(horizontal="right", vertical="center")
        gt_prof.number_format = '#,##0.00 "DH"'
        gt_prof.border = BORDER_TOTAL

    # Auto-adjust column widths
    for col in ws.columns:
        max_len = 0
        for cell in col:
            val_str = str(cell.value or '')
            if cell.number_format and "DH" in cell.number_format and isinstance(cell.value, (int, float)):
                val_str = f"{cell.value:,.2f} DH"
            max_len = max(max_len, len(val_str))
        col_letter = get_column_letter(col[0].column)
        ws.column_dimensions[col_letter].width = max(max_len + 4, 13)

    # Système de vérification et correction automatique de la feuille (lignes et colonnes)
    audit_and_correct_worksheet(ws, candidate_header_row=3)

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
            "رقم التسجيل", "اسم التلميذ (بالفرنسية)", "اسم التلميذ (بالعربية)", "ولي الأمر",
            "رقم الهاتف للمتابعة", "الأنشطة المستفاد منها", "عدد الأنشطة", "الشهر المعني (المستحق)", "الاتفاقية / سبب التخفيض",
            "الواجب الشهري (درهم)", "المبلغ المدفوع (درهم)", "الباقي المستحق (درهم)", "الحالة"
        ]
    elif lang == "bilingual":
        ws.title = "Impayés - المتأخرات"
        align_header = Alignment(horizontal="center", vertical="center", wrap_text=True)
        align_data = Alignment(horizontal="left", vertical="center")
        title_text = "GENIUS CHESS ACADEMY - جمعية الشطرنج القاسمي - Liste des Impayés / لائحة المستحقات غير المؤداة 2026"
        headers = [
            "Matricule", "Élève (FR)", "الاسم (AR)", "Parent / ولي الأمر",
            "Tél Relance", "Activités / الأنشطة", "Nb Activités / عدد الأنشطة", "Mois Concerné / الشهر المعني", "Convention / Motif Réduction",
            "Montant Dû (DH)", "Payé (DH)", "Reste Impayé (DH)", "Statut / الحالة"
        ]
    else: # fr
        ws.title = "Liste des Impayés"
        align_header = Alignment(horizontal="center", vertical="center", wrap_text=True)
        align_data = Alignment(horizontal="left", vertical="center")
        title_text = "GENIUS CHESS ACADEMY - جمعية الشطرنج القاسمي - Liste des Élèves Non-Payants & Impayés 2026"
        headers = [
            "Matricule", "Nom Élève (FR)", "Nom Élève (AR)", "Parent / Tuteur",
            "Téléphone Relance", "Activités Suivies", "Nombre d'activités", "Mois Concerné (Période)", "Convention / Motif Réduction",
            "Montant Dû (DH)", "Déjà Versé (DH)", "Reste Impayé (DH)", "Statut"
        ]

    # Sanitize and deduplicate headers
    headers, kept_indices = sanitize_header_list(headers)

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

    # Data rows (Deduplicated sources)
    invoices_list = deduplicate_items(invoices_queryset, key_func=lambda inv: getattr(inv, 'id', inv))
    row_idx = 4
    total_due = 0.0
    total_paid = 0.0
    total_balance = 0.0

    for inv in invoices_list:
        ws.row_dimensions[row_idx].height = 22
        st = inv.student
        activities_str, nb_activities, _ = get_student_activities_and_count(st, invoice=inv, lang=lang)
        parent_str = st.parent.get_name(lang) if (st and st.parent) else "-"
        phone_str = st.parent.phone if (st and st.parent) else "-"
        month_str = inv.get_period_label(lang)

        # Motif de réduction le cas échéant
        reduction_str = "-"
        if st:
            discount_val = float(inv.discount_amount) if inv.discount_amount > 0 else 0.0
            if discount_val == 0.0 and st.has_convention:
                _, disc, _ = st.calculate_monthly_fee()
                discount_val = float(disc)

            if st.has_convention and st.convention_name:
                if discount_val > 0:
                    reduction_str = f"{st.convention_name} (-{discount_val:.2f} DH)" if lang != "ar" else f"{st.convention_name} (تخفيض {discount_val:.2f} درهم)"
                else:
                    reduction_str = st.convention_name
            elif discount_val > 0:
                reduction_str = f"Réduction (-{discount_val:.2f} DH)" if lang != "ar" else f"تخفيض ({discount_val:.2f} درهم)"

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
            activities_str,
            nb_activities,
            month_str,
            reduction_str,
            amt_due,
            amt_paid,
            balance,
            status_str,
        ]
        if lang == "ar":
            row_values[1], row_values[2] = row_values[2], row_values[1]

        # Ensure strict alignment with headers
        row_values = align_row_to_headers(row_values, len(headers), kept_indices)

        for col_num, val in enumerate(row_values, 1):
            cell = ws.cell(row=row_idx, column=col_num)
            cell.value = val
            cell.font = DATA_FONT
            cell.border = BORDER_THIN
            if col_num in (10, 11):
                cell.alignment = Alignment(horizontal="right", vertical="center")
                cell.number_format = '#,##0.00 "DH"'
            elif col_num == 12:
                cell.alignment = Alignment(horizontal="right", vertical="center")
                cell.number_format = '#,##0.00 "DH"'
                cell.font = Font(name="Segoe UI", size=10, bold=True, color="991B1B")
            elif col_num == 7:
                cell.alignment = Alignment(horizontal="center", vertical="center")
                cell.font = BOLD_DATA_FONT
            else:
                cell.alignment = align_data
        row_idx += 1

    # Total Summary Row
    ws.row_dimensions[row_idx].height = 28
    ws.merge_cells(start_row=row_idx, start_column=1, end_row=row_idx, end_column=9)
    tot_label = ws.cell(row=row_idx, column=1)
    tot_label.value = "TOTAL DES IMPAYÉS RESTANTS / مجموع المتأخرات المتبقية :" if lang != "ar" else "مجموع المتأخرات المتبقية المستحقة :"
    tot_label.font = TOTAL_RED_FONT
    tot_label.fill = UNPAID_TOTAL_FILL
    tot_label.alignment = Alignment(horizontal="right" if lang != "ar" else "left", vertical="center")
    tot_label.border = BORDER_TOTAL

    for c in range(1, 10):
        ws.cell(row=row_idx, column=c).border = BORDER_TOTAL
        ws.cell(row=row_idx, column=c).fill = UNPAID_TOTAL_FILL

    tot_due_cell = ws.cell(row=row_idx, column=10)
    tot_due_cell.value = total_due
    tot_due_cell.font = BOLD_DATA_FONT
    tot_due_cell.fill = UNPAID_TOTAL_FILL
    tot_due_cell.alignment = Alignment(horizontal="right", vertical="center")
    tot_due_cell.number_format = '#,##0.00 "DH"'
    tot_due_cell.border = BORDER_TOTAL

    tot_paid_cell = ws.cell(row=row_idx, column=11)
    tot_paid_cell.value = total_paid
    tot_paid_cell.font = BOLD_DATA_FONT
    tot_paid_cell.fill = UNPAID_TOTAL_FILL
    tot_paid_cell.alignment = Alignment(horizontal="right", vertical="center")
    tot_paid_cell.number_format = '#,##0.00 "DH"'
    tot_paid_cell.border = BORDER_TOTAL

    tot_bal_cell = ws.cell(row=row_idx, column=12)
    tot_bal_cell.value = total_balance
    tot_bal_cell.font = TOTAL_RED_FONT
    tot_bal_cell.fill = UNPAID_TOTAL_FILL
    tot_bal_cell.alignment = Alignment(horizontal="right", vertical="center")
    tot_bal_cell.number_format = '#,##0.00 "DH"'
    tot_bal_cell.border = BORDER_TOTAL

    ws.cell(row=row_idx, column=13).border = BORDER_TOTAL
    ws.cell(row=row_idx, column=13).fill = UNPAID_TOTAL_FILL

    # Système de vérification et correction automatique de la feuille (lignes et colonnes)
    audit_and_correct_worksheet(ws, candidate_header_row=3)

    buffer = io.BytesIO()
    wb.save(buffer)
    excel_bytes = buffer.getvalue()
    buffer.close()
    return excel_bytes
