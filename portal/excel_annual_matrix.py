import io
import re
from datetime import date, datetime
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

from academy.models import Group, Student, Attendance, SessionSchedule
from finance.models import Invoice, Payment, PaymentExemption
from core.i18n import FRENCH_MONTHS, ARABIC_MONTHS


# Couleurs et styles cohérents avec la charte GCA
NAVY_DARK = "0A192F"
NAVY_MID = "1E3A8A"
SUBHEADER_BG = "E2E8F0"
GROUP_BANNER_BG = "EFF6FF"
BORDER_COLOR = "94A3B8"
BORDER_LIGHT = "CBD5E1"

FILL_NAVY = PatternFill(start_color=NAVY_DARK, end_color=NAVY_DARK, fill_type="solid")
FILL_NAVY_MID = PatternFill(start_color=NAVY_MID, end_color=NAVY_MID, fill_type="solid")
FILL_SUBHEADER = PatternFill(start_color=SUBHEADER_BG, end_color=SUBHEADER_BG, fill_type="solid")
FILL_GROUP_BANNER = PatternFill(start_color=GROUP_BANNER_BG, end_color=GROUP_BANNER_BG, fill_type="solid")
FILL_ZEBRA = PatternFill(start_color="F8FAFC", end_color="F8FAFC", fill_type="solid")

# Couleurs présences
FILL_PRESENT = PatternFill(start_color="DCFCE7", end_color="DCFCE7", fill_type="solid")
FONT_PRESENT = Font(name="Calibri", size=10, bold=True, color="166534")

FILL_ABSENT = PatternFill(start_color="FEE2E2", end_color="FEE2E2", fill_type="solid")
FONT_ABSENT = Font(name="Calibri", size=10, bold=True, color="991B1B")

FILL_LATE = PatternFill(start_color="FFEDD5", end_color="FFEDD5", fill_type="solid")
FONT_LATE = Font(name="Calibri", size=10, bold=True, color="9A3412")

FILL_JUSTIFIED = PatternFill(start_color="E0E7FF", end_color="E0E7FF", fill_type="solid")
FONT_JUSTIFIED = Font(name="Calibri", size=10, bold=True, color="3730A3")

# Couleurs paiements
FILL_PAID = PatternFill(start_color="DCFCE7", end_color="DCFCE7", fill_type="solid")
FONT_PAID = Font(name="Calibri", size=9, bold=True, color="166534")

FILL_UNPAID = PatternFill(start_color="FEE2E2", end_color="FEE2E2", fill_type="solid")
FONT_UNPAID = Font(name="Calibri", size=9, bold=True, color="991B1B")

FILL_PARTIAL = PatternFill(start_color="FEF3C7", end_color="FEF3C7", fill_type="solid")
FONT_PARTIAL = Font(name="Calibri", size=9, bold=True, color="92400E")

FILL_EXEMPT = PatternFill(start_color="E0F2FE", end_color="E0F2FE", fill_type="solid")
FONT_EXEMPT = Font(name="Calibri", size=8, bold=True, color="0369A1")

# Bordures
THIN_SIDE = Side(style="thin", color=BORDER_LIGHT)
MED_NAVY_SIDE = Side(style="medium", color=NAVY_DARK)

CELL_BORDER = Border(left=THIN_SIDE, right=THIN_SIDE, top=THIN_SIDE, bottom=THIN_SIDE)
HEADER_BORDER = Border(left=THIN_SIDE, right=THIN_SIDE, top=MED_NAVY_SIDE, bottom=THIN_SIDE)
MONTH_END_BORDER = Border(left=THIN_SIDE, right=MED_NAVY_SIDE, top=THIN_SIDE, bottom=THIN_SIDE)


def _safe_sheet_title(raw_title, existing_titles):
    """Nettoie un nom d'onglet Excel (<= 31 caractères, sans caractères interdits, unique)."""
    cleaned = re.sub(r'[\\/*?:\[\]]', '-', str(raw_title or 'Onglet')).strip()
    if not cleaned:
        cleaned = "Onglet"
    base = cleaned[:31]
    candidate = base
    idx = 2
    while candidate in existing_titles:
        suffix = f" ({idx})"
        candidate = f"{base[:31 - len(suffix)]}{suffix}"
        idx += 1
    existing_titles.add(candidate)
    return candidate


def _get_academic_months(academic_start_year):
    """Retourne la liste des (month, year) de Septembre Y à Juin Y+1."""
    return [
        (9, academic_start_year),
        (10, academic_start_year),
        (11, academic_start_year),
        (12, academic_start_year),
        (1, academic_start_year + 1),
        (2, academic_start_year + 1),
        (3, academic_start_year + 1),
        (4, academic_start_year + 1),
        (5, academic_start_year + 1),
        (6, academic_start_year + 1),
    ]


def _attendance_code(status):
    return {
        'present': 'P',
        'absent': 'A',
        'late': 'R',
        'justified': 'J',
    }.get(status, '')


def _apply_attendance_style(cell, code):
    if not code:
        return
    primary = code.split('/')[0].strip()
    if primary == 'P':
        cell.fill = FILL_PRESENT
        cell.font = FONT_PRESENT
    elif primary == 'A':
        cell.fill = FILL_ABSENT
        cell.font = FONT_ABSENT
    elif primary == 'R':
        cell.fill = FILL_LATE
        cell.font = FONT_LATE
    elif primary == 'J':
        cell.fill = FILL_JUSTIFIED
        cell.font = FONT_JUSTIFIED


def _resolve_payment_state(student_id, group_id, year, month, today,
                           exemptions_set, inv_by_stu_grp, inv_by_stu, payments_set):
    """
    Détermine l'état de paiement d'un élève pour un mois donné.
    Retourne un tuple (col_target, label, fill, font) où col_target vaut 'oui', 'non' ou None.
    """
    if (student_id, year, month) in exemptions_set:
        return 'oui', 'EXONÉRÉ', FILL_EXEMPT, FONT_EXEMPT

    inv = None
    if group_id is not None:
        inv = inv_by_stu_grp.get((student_id, group_id, year, month))
    if inv is None:
        inv = inv_by_stu.get((student_id, year, month))

    if inv is not None:
        if inv.is_exempt or inv.status == 'exempt':
            return 'oui', 'EXONÉRÉ', FILL_EXEMPT, FONT_EXEMPT
        if inv.status == 'paid':
            return 'oui', 'OUI', FILL_PAID, FONT_PAID
        if inv.status == 'partial':
            return 'oui', 'PARTIEL', FILL_PARTIAL, FONT_PARTIAL
        # status == 'unpaid'
        return 'non', 'NON', FILL_UNPAID, FONT_UNPAID

    if (student_id, year, month) in payments_set:
        return 'oui', 'OUI', FILL_PAID, FONT_PAID

    # Aucun paiement ni facture : si mois passé ou en cours -> NON, si mois futur -> vide
    if (year, month) <= (today.year, today.month):
        return 'non', 'NON', FILL_UNPAID, FONT_UNPAID
    return None, '', None, None


def _build_sheet_for_groups(ws, blocks, months_list, today, preloaded_data, lang="fr", academic_start_year=2026):
    """
    Construit une feuille Excel complète contenant une suite de tableaux
    (un par groupe), classés par Activité puis Groupe.
    """
    ws.views.sheetView[0].showGridLines = True
    if lang == "ar":
        ws.sheet_view.rightToLeft = True

    total_cols = 2 + len(months_list) * 6
    last_col_letter = get_column_letter(total_cols)

    # Largeurs de colonnes
    ws.column_dimensions['A'].width = 5
    ws.column_dimensions['B'].width = 28
    for m_idx in range(len(months_list)):
        base_col = 3 + m_idx * 6
        for s_off in range(4):
            ws.column_dimensions[get_column_letter(base_col + s_off)].width = 4.5
        ws.column_dimensions[get_column_letter(base_col + 4)].width = 8.5  # OUI / EXONÉRÉ
        ws.column_dimensions[get_column_letter(base_col + 5)].width = 5.5  # NON

    # Bannière titre principal
    ws.merge_cells(f"A1:{last_col_letter}1")
    c_title = ws["A1"]
    c_title.value = (
        f"GENIUS CHESS ACADEMY — SUIVI ANNUEL PRÉSENCES & PAIEMENTS ({academic_start_year}-{academic_start_year + 1})"
        if lang != "ar" else
        f"جمعية الشطرنج القاسمي — التتبع السنوي للحضور والأداءات ({academic_start_year}-{academic_start_year + 1})"
    )
    c_title.font = Font(name="Calibri", size=14, bold=True, color="FFFFFF")
    c_title.fill = FILL_NAVY
    c_title.alignment = Alignment(horizontal="center", vertical="center")
    ws.row_dimensions[1].height = 30

    ws.merge_cells(f"A2:{last_col_letter}2")
    c_sub = ws["A2"]
    c_sub.value = (
        f"Légende Présence : P = Présent | A = Absent | R = Retard | J = Justifié  •  "
        f"Paiement : OUI / NON / PARTIEL / EXONÉRÉ  •  Généré le {datetime.now().strftime('%d/%m/%Y à %H:%M')}"
    )
    c_sub.font = Font(name="Calibri", size=10, italic=True, color="0A192F")
    c_sub.fill = FILL_SUBHEADER
    c_sub.alignment = Alignment(horizontal="center", vertical="center")
    ws.row_dimensions[2].height = 20

    # Figer la colonne N° et Nom & Prénom pour scroller facilement à travers les mois
    ws.freeze_panes = "C3"

    curr_row = 4

    group_month_dates = preloaded_data['group_month_dates']
    att_map = preloaded_data['att_map']
    exemptions_set = preloaded_data['exemptions_set']
    inv_by_stu_grp = preloaded_data['inv_by_stu_grp']
    inv_by_stu = preloaded_data['inv_by_stu']
    payments_set = preloaded_data['payments_set']

    month_dict = ARABIC_MONTHS if lang == "ar" else FRENCH_MONTHS

    for block in blocks:
        group = block['group']
        subject_name = block['subject_name']
        group_name = block['group_name']
        trainers_str = block['trainers']
        students = block['students']

        # 1. Bandeau Matière / Professeur / Groupe
        ws.merge_cells(start_row=curr_row, start_column=1, end_row=curr_row, end_column=total_cols)
        banner_cell = ws.cell(row=curr_row, column=1)
        banner_cell.value = (
            f"ACTIVITÉ / MATIÈRE : {subject_name}    |    PROFESSEUR : {trainers_str}    |    GROUPE : {group_name}    ({len(students)} élève(s))"
        )
        banner_cell.font = Font(name="Calibri", size=11, bold=True, color="0A192F")
        banner_cell.fill = FILL_GROUP_BANNER
        banner_cell.alignment = Alignment(horizontal="left", vertical="center", indent=1)
        for col_i in range(1, total_cols + 1):
            ws.cell(row=curr_row, column=col_i).border = HEADER_BORDER
            ws.cell(row=curr_row, column=col_i).fill = FILL_GROUP_BANNER
        ws.row_dimensions[curr_row].height = 24
        curr_row += 1

        # 2. Lignes d'en-tête du tableau (3 lignes : Mois / S1..S4+Payé / Présence+OUI/NON)
        row_months = curr_row
        row_subs = curr_row + 1
        row_labels = curr_row + 2

        ws.row_dimensions[row_months].height = 22
        ws.row_dimensions[row_subs].height = 20
        ws.row_dimensions[row_labels].height = 20

        # Colonnes fixes A & B fusionnées verticalement sur les 3 lignes d'en-tête
        ws.merge_cells(start_row=row_months, start_column=1, end_row=row_labels, end_column=1)
        c_no = ws.cell(row=row_months, column=1, value="N°")
        c_no.font = Font(name="Calibri", size=10, bold=True, color="FFFFFF")
        c_no.fill = FILL_NAVY
        c_no.alignment = Alignment(horizontal="center", vertical="center")

        ws.merge_cells(start_row=row_months, start_column=2, end_row=row_labels, end_column=2)
        c_name = ws.cell(row=row_months, column=2, value="NOM ET PRENOM" if lang != "ar" else "الاسم الكامل")
        c_name.font = Font(name="Calibri", size=10, bold=True, color="FFFFFF")
        c_name.fill = FILL_NAVY
        c_name.alignment = Alignment(horizontal="center", vertical="center")

        for r_i in range(row_months, row_labels + 1):
            ws.cell(row=r_i, column=1).border = CELL_BORDER
            ws.cell(row=r_i, column=2).border = CELL_BORDER

        # En-têtes pour chaque mois
        for m_idx, (m_num, y_num) in enumerate(months_list):
            base_col = 3 + m_idx * 6
            m_label = f"{month_dict.get(m_num, str(m_num)).capitalize()} {y_num}"

            # Ligne Mois (fusionnée sur 6 colonnes)
            ws.merge_cells(start_row=row_months, start_column=base_col, end_row=row_months, end_column=base_col + 5)
            cm = ws.cell(row=row_months, column=base_col, value=m_label)
            cm.font = Font(name="Calibri", size=10, bold=True, color="FFFFFF")
            cm.fill = FILL_NAVY_MID if m_idx % 2 == 0 else FILL_NAVY
            cm.alignment = Alignment(horizontal="center", vertical="center")
            for c_off in range(6):
                cell_m = ws.cell(row=row_months, column=base_col + c_off)
                cell_m.fill = FILL_NAVY_MID if m_idx % 2 == 0 else FILL_NAVY
                cell_m.border = MONTH_END_BORDER if c_off == 5 else CELL_BORDER

            # Ligne S1..S4 + Payé
            for s_off in range(4):
                cs = ws.cell(row=row_subs, column=base_col + s_off, value=f"S{s_off + 1}")
                cs.font = Font(name="Calibri", size=9, bold=True, color="0A192F")
                cs.fill = FILL_SUBHEADER
                cs.alignment = Alignment(horizontal="center", vertical="center")
                cs.border = CELL_BORDER

            ws.merge_cells(start_row=row_subs, start_column=base_col + 4, end_row=row_subs, end_column=base_col + 5)
            cp = ws.cell(row=row_subs, column=base_col + 4, value="Payé" if lang != "ar" else "الأداء")
            cp.font = Font(name="Calibri", size=9, bold=True, color="0A192F")
            cp.fill = FILL_SUBHEADER
            cp.alignment = Alignment(horizontal="center", vertical="center")
            ws.cell(row=row_subs, column=base_col + 4).border = CELL_BORDER
            ws.cell(row=row_subs, column=base_col + 5).fill = FILL_SUBHEADER
            ws.cell(row=row_subs, column=base_col + 5).border = MONTH_END_BORDER

            # Ligne Présence (fusionnée sur S1..S4) + OUI / NON
            ws.merge_cells(start_row=row_labels, start_column=base_col, end_row=row_labels, end_column=base_col + 3)
            cpr = ws.cell(row=row_labels, column=base_col, value="présence" if lang != "ar" else "الحضور")
            cpr.font = Font(name="Calibri", size=9, italic=True, bold=True, color="334155")
            cpr.fill = FILL_GROUP_BANNER
            cpr.alignment = Alignment(horizontal="center", vertical="center")
            for c_off in range(4):
                ws.cell(row=row_labels, column=base_col + c_off).fill = FILL_GROUP_BANNER
                ws.cell(row=row_labels, column=base_col + c_off).border = CELL_BORDER

            co = ws.cell(row=row_labels, column=base_col + 4, value="OUI")
            co.font = Font(name="Calibri", size=8, bold=True, color="166534")
            co.fill = FILL_PAID
            co.alignment = Alignment(horizontal="center", vertical="center")
            co.border = CELL_BORDER

            cn = ws.cell(row=row_labels, column=base_col + 5, value="NON")
            cn.font = Font(name="Calibri", size=8, bold=True, color="991B1B")
            cn.fill = FILL_UNPAID
            cn.alignment = Alignment(horizontal="center", vertical="center")
            cn.border = MONTH_END_BORDER

        curr_row += 3

        # 3. Lignes des élèves du groupe
        if not students:
            ws.merge_cells(start_row=curr_row, start_column=1, end_row=curr_row, end_column=total_cols)
            empty_cell = ws.cell(row=curr_row, column=1, value="Aucun élève inscrit dans ce groupe.")
            empty_cell.font = Font(name="Calibri", size=10, italic=True, color="64748B")
            empty_cell.alignment = Alignment(horizontal="center", vertical="center")
            ws.row_dimensions[curr_row].height = 20
            curr_row += 2
            continue

        group_id = group.id if group else None

        for idx, st in enumerate(students, start=1):
            ws.row_dimensions[curr_row].height = 20
            is_zebra = (idx % 2 == 0)

            c_idx = ws.cell(row=curr_row, column=1, value=idx)
            c_idx.font = Font(name="Calibri", size=10, bold=True, color="475569")
            c_idx.alignment = Alignment(horizontal="center", vertical="center")
            c_idx.border = CELL_BORDER
            if is_zebra:
                c_idx.fill = FILL_ZEBRA

            st_name = st.get_full_name("ar" if lang == "ar" else "fr")
            c_st = ws.cell(row=curr_row, column=2, value=st_name)
            c_st.font = Font(name="Calibri", size=10, bold=True, color="0F172A")
            c_st.alignment = Alignment(horizontal="right" if lang == "ar" else "left", vertical="center")
            c_st.border = CELL_BORDER
            if is_zebra:
                c_st.fill = FILL_ZEBRA

            for m_idx, (m_num, y_num) in enumerate(months_list):
                base_col = 3 + m_idx * 6

                # Dates de séances du groupe dans ce mois
                dates_in_month = group_month_dates.get((group_id, y_num, m_num), []) if group_id else []
                # Remplir S1, S2, S3, S4
                for s_off in range(4):
                    cell_s = ws.cell(row=curr_row, column=base_col + s_off)
                    cell_s.alignment = Alignment(horizontal="center", vertical="center")
                    cell_s.border = CELL_BORDER
                    if is_zebra:
                        cell_s.fill = FILL_ZEBRA

                    val = ""
                    if s_off < len(dates_in_month):
                        if s_off == 3 and len(dates_in_month) > 4:
                            # S'il y a une 5ème séance dans le mois, combiner dans S4
                            codes = [att_map.get((st.id, group_id, d), '') for d in dates_in_month[3:]]
                            codes = [c for c in codes if c]
                            val = "/".join(codes)
                        else:
                            val = att_map.get((st.id, group_id, dates_in_month[s_off]), '')

                    if val:
                        cell_s.value = val
                        _apply_attendance_style(cell_s, val)

                # État de paiement OUI / NON
                cell_oui = ws.cell(row=curr_row, column=base_col + 4)
                cell_non = ws.cell(row=curr_row, column=base_col + 5)
                cell_oui.alignment = Alignment(horizontal="center", vertical="center")
                cell_non.alignment = Alignment(horizontal="center", vertical="center")
                cell_oui.border = CELL_BORDER
                cell_non.border = MONTH_END_BORDER
                if is_zebra:
                    cell_oui.fill = FILL_ZEBRA
                    cell_non.fill = FILL_ZEBRA

                target, pay_label, pay_fill, pay_font = _resolve_payment_state(
                    st.id, group_id, y_num, m_num, today,
                    exemptions_set, inv_by_stu_grp, inv_by_stu, payments_set
                )
                if target == 'oui':
                    cell_oui.value = pay_label
                    cell_oui.fill = pay_fill
                    cell_oui.font = pay_font
                elif target == 'non':
                    cell_non.value = pay_label
                    cell_non.fill = pay_fill
                    cell_non.font = pay_font

            curr_row += 1

        # Ligne vide de séparation entre deux groupes
        ws.row_dimensions[curr_row].height = 14
        curr_row += 1


def generate_annual_tracking_excel(groups_queryset=None, academic_start_year=None, lang="fr", include_unassigned=True):
    """
    Génère un classeur Excel (.xlsx) complet contenant tous les élèves groupés et
    classés par Activités et Groupes, avec :
    - Une colonne par mois (Septembre à Juin)
    - Sous-colonnes S1..S4 pour les présences (P, A, R, J)
    - Sous-colonnes Payé (OUI / NON / EXONÉRÉ / PARTIEL)
    """
    today = date.today()
    if academic_start_year is None:
        academic_start_year = today.year if today.month >= 9 else today.year - 1

    months_list = _get_academic_months(academic_start_year)
    start_date = date(academic_start_year, 9, 1)
    end_date = date(academic_start_year + 1, 6, 30)

    if groups_queryset is None:
        groups_qs = Group.objects.select_related('subject', 'level').prefetch_related(
            'schedules', 'students'
        ).order_by('subject__name_fr', 'name_fr')
    else:
        groups_qs = groups_queryset.select_related('subject', 'level').prefetch_related(
            'schedules', 'students'
        ).order_by('subject__name_fr', 'name_fr')

    groups_list = list(groups_qs)

    # Précharger toutes les présences de l'année académique en une seule requête
    att_qs = Attendance.objects.filter(
        date__gte=start_date,
        date__lte=end_date,
    ).select_related('session').order_by('date', 'id')

    group_month_dates_set = {}
    att_map = {}
    for att in att_qs:
        g_id = att.session.group_id
        d = att.date
        key_gm = (g_id, d.year, d.month)
        if key_gm not in group_month_dates_set:
            group_month_dates_set[key_gm] = set()
        group_month_dates_set[key_gm].add(d)

        code = _attendance_code(att.status)
        if code:
            att_map[(att.student_id, g_id, d)] = code

    group_month_dates = {k: sorted(v) for k, v in group_month_dates_set.items()}

    # Précharger les exonérations, factures et paiements pour l'année académique
    years_in_scope = {academic_start_year, academic_start_year + 1}

    exemptions_set = set(
        PaymentExemption.objects.filter(period_year__in=years_in_scope)
        .values_list('student_id', 'period_year', 'period_month')
    )

    inv_by_stu_grp = {}
    inv_by_stu = {}
    for inv in Invoice.objects.filter(period_year__in=years_in_scope).order_by('id'):
        inv_by_stu_grp[(inv.student_id, inv.group_id, inv.period_year, inv.period_month)] = inv
        # Prioriser une facture réglée ou exonérée si l'élève a plusieurs factures sur le même mois
        existing = inv_by_stu.get((inv.student_id, inv.period_year, inv.period_month))
        if existing is None or inv.status in ('paid', 'exempt'):
            inv_by_stu[(inv.student_id, inv.period_year, inv.period_month)] = inv

    payments_set = set()
    for pay in Payment.objects.filter(period_year__in=years_in_scope, amount__gt=0).select_related('invoice'):
        pm = pay.period_month or (pay.invoice.period_month if pay.invoice else None)
        py = pay.period_year or (pay.invoice.period_year if pay.invoice else None)
        if pm and py:
            payments_set.add((pay.student_id, py, pm))

    preloaded_data = {
        'group_month_dates': group_month_dates,
        'att_map': att_map,
        'exemptions_set': exemptions_set,
        'inv_by_stu_grp': inv_by_stu_grp,
        'inv_by_stu': inv_by_stu,
        'payments_set': payments_set,
    }

    # Construire les blocs par groupe
    blocks = []
    assigned_student_ids = set()

    for grp in groups_list:
        trainers = []
        seen_t = set()
        for sch in grp.schedules.all():
            t_name = sch.get_trainer_name("ar" if lang == "ar" else "fr")
            if t_name and t_name not in seen_t:
                seen_t.add(t_name)
                trainers.append(t_name)
        trainers_str = ", ".join(trainers) if trainers else ("Non assigné" if lang != "ar" else "غير محدد")

        students_in_grp = [s for s in grp.students.all() if s.active]
        students_in_grp.sort(key=lambda s: (s.last_name_fr.casefold(), s.first_name_fr.casefold()))
        for s in students_in_grp:
            assigned_student_ids.add(s.id)

        subject_name = grp.subject.get_name("ar" if lang == "ar" else "fr") if grp.subject else "-"
        group_name = grp.get_name("ar" if lang == "ar" else "fr")

        blocks.append({
            'group': grp,
            'subject_id': grp.subject_id,
            'subject_name': subject_name,
            'group_name': group_name,
            'trainers': trainers_str,
            'students': students_in_grp,
        })

    # Ajouter les élèves actifs sans groupe si demandé
    if include_unassigned:
        unassigned = list(
            Student.objects.filter(active=True)
            .exclude(id__in=assigned_student_ids)
            .order_by('last_name_fr', 'first_name_fr')
        )
        if unassigned:
            blocks.append({
                'group': None,
                'subject_id': None,
                'subject_name': "Non affecté" if lang != "ar" else "بدون مجموعة",
                'group_name': "Élèves sans groupe" if lang != "ar" else "تلاميذ بدون فوج",
                'trainers': "-",
                'students': unassigned,
            })

    wb = Workbook()
    existing_titles = set()

    # Onglet 1 : Suivi Global
    ws_global = wb.active
    ws_global.title = _safe_sheet_title(
        "Suivi Global" if lang != "ar" else "التتبع الشامل",
        existing_titles
    )
    _build_sheet_for_groups(
        ws_global, blocks, months_list, today, preloaded_data,
        lang=lang, academic_start_year=academic_start_year
    )

    # Onglets par Activité (si plus d'une activité ou pour faciliter l'impression par matière)
    blocks_by_subject = {}
    for b in blocks:
        s_key = b['subject_name']
        if s_key not in blocks_by_subject:
            blocks_by_subject[s_key] = []
        blocks_by_subject[s_key].append(b)

    if len(blocks_by_subject) > 1:
        for subj_name, subj_blocks in blocks_by_subject.items():
            ws_subj = wb.create_sheet(title=_safe_sheet_title(subj_name, existing_titles))
            _build_sheet_for_groups(
                ws_subj, subj_blocks, months_list, today, preloaded_data,
                lang=lang, academic_start_year=academic_start_year
            )

    output = io.BytesIO()
    wb.save(output)
    output.seek(0)
    return output.getvalue()
