import logging
from openpyxl.worksheet.cell_range import CellRange
from openpyxl.utils import get_column_letter

logger = logging.getLogger(__name__)

# Mots-clés désignant des lignes de synthèse/totaux à NE JAMAIS considérer comme des doublons de données
SUMMARY_KEYWORDS = (
    "total", "totaux", "sous-total", "chiffre d'affaires", "recettes", "impayés",
    "مجموع", "المجموع", "إجمالي", "النسبة", "حصيلة", "taux de recouvrement"
)


def deduplicate_items(iterable, key_func=None):
    """
    Déduplique un QuerySet ou une liste d'éléments en préservant l'ordre d'origine.
    Utilise soit une fonction clé personnalisée, soit la clé primaire Django (pk / id),
    soit l'objet lui-même.
    """
    if iterable is None:
        return []

    seen = set()
    deduped = []

    for item in iterable:
        if key_func is not None:
            key = key_func(item)
        elif hasattr(item, 'pk') and item.pk is not None:
            key = (item.__class__.__name__, item.pk)
        elif hasattr(item, 'id') and item.id is not None:
            key = (item.__class__.__name__, item.id)
        else:
            key = item

        if key not in seen:
            seen.add(key)
            deduped.append(item)
        else:
            logger.warning("Doublon détecté et écarté dans les données sources : %s", key)

    return deduped


def sanitize_header_list(headers):
    """
    Vérifie et corrige la liste des en-têtes de colonnes :
    - Élimine les colonnes en double (titre d'en-tête identique).
    - Retourne les en-têtes dédupliqués et la liste des indices de colonnes conservés.
    """
    seen_headers = set()
    cleaned_headers = []
    kept_indices = []

    for idx, h in enumerate(headers):
        # Supporte format str ou tuple (title, width)
        h_title = h[0] if isinstance(h, (list, tuple)) else str(h)
        norm_key = h_title.strip().casefold()

        if norm_key not in seen_headers:
            seen_headers.add(norm_key)
            cleaned_headers.append(h)
            kept_indices.append(idx)
        else:
            logger.warning("Colonne d'en-tête en double détectée et supprimée : '%s' à l'indice %d", h_title, idx)

    return cleaned_headers, kept_indices


def align_row_to_headers(row_values, expected_col_count, kept_indices=None):
    """
    Garantit l'alignement strict entre les valeurs de la ligne et le nombre de colonnes d'en-tête :
    - Si kept_indices est fourni, ne retient que les colonnes correspondantes.
    - Si trop de colonnes : tronque l'excédent.
    - Si colonnes manquantes : complète avec des chaînes vides.
    """
    if kept_indices is not None and len(kept_indices) < len(row_values):
        values = [row_values[i] for i in kept_indices if i < len(row_values)]
    else:
        values = list(row_values)

    if len(values) > expected_col_count:
        values = values[:expected_col_count]
    elif len(values) < expected_col_count:
        values.extend([''] * (expected_col_count - len(values)))

    return values


def is_summary_or_title_row(row_cells):
    """
    Vérifie si une ligne est une ligne de titre général ou de total/synthèse
    qu'il faut impérativement préserver.
    """
    non_empty = [c for c in row_cells if c.value is not None and str(c.value).strip() != '']
    if not non_empty:
        return True  # Ligne vide

    # Si la ligne ne contient qu'une seule cellule renseignée (souvent un titre de section ou bannière)
    if len(non_empty) == 1:
        return True

    # Vérification des mots-clés de synthèse dans les premières cellules
    first_vals = " ".join(str(c.value or '').casefold() for c in non_empty[:3])
    for kw in SUMMARY_KEYWORDS:
        if kw in first_vals:
            return True

    return False


def repair_merged_cells(ws):
    """
    Corrige les plages fusionnées de la feuille Excel après suppression
    éventuelle de lignes ou de colonnes, afin d'éviter tout fichier corrompu.
    """
    ranges_to_remove = []
    ranges_to_add = []

    for mr in list(ws.merged_cells.ranges):
        # Si la plage dépasse la taille actuelle de la feuille
        if mr.max_col > ws.max_column or mr.max_row > ws.max_row:
            ranges_to_remove.append(mr)
            new_max_col = min(mr.max_col, ws.max_column)
            new_max_row = min(mr.max_row, ws.max_row)
            # Ne réinsérer que si la plage fusionne au moins 2 cellules
            if new_max_col > mr.min_col or new_max_row > mr.min_row:
                ranges_to_add.append(
                    CellRange(
                        min_col=mr.min_col,
                        min_row=mr.min_row,
                        max_col=new_max_col,
                        max_row=new_max_row
                    )
                )
        # Supprimer les fusions dégénérées 1x1
        elif mr.min_col == mr.max_col and mr.min_row == mr.max_row:
            ranges_to_remove.append(mr)

    for r in ranges_to_remove:
        try:
            ws.merged_cells.ranges.remove(r)
        except (KeyError, ValueError):
            pass

    for r in ranges_to_add:
        try:
            ws.merged_cells.ranges.add(r)
        except Exception:
            pass


def audit_and_correct_worksheet(ws, candidate_header_row=None):
    """
    Inspecte et corrige directement une feuille openpyxl :
    1. Détecte et supprime les colonnes dupliquées (même en-tête ou contenu 100% identique).
    2. Détecte et supprime les lignes de données dupliquées.
    3. Répare les cellules fusionnées.
    4. Réajuste les dimensions des colonnes.
    Retourne un dictionnaire récapitulatif des corrections appliquées.
    """
    audit_report = {
        'sheet_title': ws.title,
        'duplicate_cols_removed': 0,
        'duplicate_rows_removed': 0,
        'status': 'clean'
    }

    if ws.max_row < 2 or ws.max_column < 1:
        return audit_report

    # A. Détection de la ligne d'en-tête principale
    header_row_idx = candidate_header_row
    if header_row_idx is None:
        # Recherche parmi les 10 premières lignes celle qui a le plus de cellules non vides
        best_count = 0
        best_row = 3
        for r in range(1, min(10, ws.max_row + 1)):
            row_cells = [ws.cell(row=r, column=c) for c in range(1, ws.max_column + 1)]
            non_empty_count = sum(1 for c in row_cells if c.value is not None and str(c.value).strip() != '')
            # Une ligne d'en-tête a généralement plusieurs cellules et n'est pas une simple fusion 1 cellule
            if non_empty_count > best_count and non_empty_count >= 3:
                best_count = non_empty_count
                best_row = r
        header_row_idx = best_row

    # B. Détection et suppression des colonnes dupliquées
    header_values = {}
    cols_to_delete = []

    for c in range(1, ws.max_column + 1):
        cell_val = ws.cell(row=header_row_idx, column=c).value
        val_str = str(cell_val or '').strip().casefold()
        if not val_str:
            continue

        if val_str in header_values:
            # Colonne en doublon détectée !
            cols_to_delete.append(c)
            logger.warning("Worksheet '%s' : Colonne #%d en double ('%s') détectée.", ws.title, c, val_str)
        else:
            header_values[val_str] = c

    # Supprimer les colonnes de droite à gauche pour ne pas fausser les indices
    for col_idx in sorted(cols_to_delete, reverse=True):
        ws.delete_cols(col_idx, 1)
        audit_report['duplicate_cols_removed'] += 1

    # C. Détection et suppression des lignes de données dupliquées
    seen_row_signatures = set()
    rows_to_delete = []

    for r in range(header_row_idx + 1, ws.max_row + 1):
        row_cells = [ws.cell(row=r, column=c) for c in range(1, ws.max_column + 1)]

        # Ne jamais supprimer les lignes de totaux, résumés, titres de sections ou séparateurs
        if is_summary_or_title_row(row_cells):
            continue

        # Signature de la ligne basée sur les valeurs textuelles de chaque cellule
        signature_items = []
        for cell in row_cells:
            v = cell.value
            if v is None:
                signature_items.append('')
            elif isinstance(v, (int, float)):
                signature_items.append(f"{v:.4f}")
            else:
                signature_items.append(str(v).strip().casefold())

        row_signature = tuple(signature_items)

        if row_signature in seen_row_signatures:
            rows_to_delete.append(r)
            logger.warning("Worksheet '%s' : Ligne #%d en double détectée et marquée pour suppression.", ws.title, r)
        else:
            seen_row_signatures.add(row_signature)

    # Supprimer les lignes de bas en haut
    for row_idx in sorted(rows_to_delete, reverse=True):
        ws.delete_rows(row_idx, 1)
        audit_report['duplicate_rows_removed'] += 1

    # D. Réparation des cellules fusionnées
    repair_merged_cells(ws)

    # E. Réajustement des largeurs de colonnes
    try:
        for col in ws.columns:
            max_len = 0
            for cell in col:
                val_str = str(cell.value or '')
                if cell.number_format and "DH" in cell.number_format and isinstance(cell.value, (int, float)):
                    val_str = f"{cell.value:,.2f} DH"
                max_len = max(max_len, len(val_str))
            col_letter = get_column_letter(col[0].column)
            ws.column_dimensions[col_letter].width = max(max_len + 4, 12)
    except Exception as e:
        logger.debug("Ajustement des largeurs colonnes ignoré : %s", e)

    if audit_report['duplicate_cols_removed'] > 0 or audit_report['duplicate_rows_removed'] > 0:
        audit_report['status'] = 'corrected'

    return audit_report


def audit_and_correct_workbook(wb):
    """
    Applique la vérification et correction automatique sur tous les onglets du classeur.
    """
    reports = []
    for sheet in wb.worksheets:
        rep = audit_and_correct_worksheet(sheet)
        reports.append(rep)
    return reports
