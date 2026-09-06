import urllib.parse
from decimal import Decimal
from datetime import datetime, date
from django.conf import settings
from academy.models import Notification
from finance.models import Invoice
from academy.whatsapp_reminders import format_phone_for_whatsapp, send_whatsapp_via_gateway
from core.i18n import format_currency


def build_unpaid_reminder_message(invoice, lang="fr"):
    """
    Construit un message de relance d'impayé amical, court, bienveillant et clair.
    Modèle inspiré du format souhaité :
    « Bonjour M./Mme X, petit rappel amical concernant la cotisation d'échecs de Lina pour le mois en cours... »
    """
    student = invoice.student
    parent = student.parent
    p_name_fr = parent.full_name_fr if parent else "Parent"
    p_name_ar = parent.full_name_ar if parent else "ولي الأمر"
    st_name_fr = student.get_full_name("fr")
    st_name_ar = student.get_full_name("ar")

    period_fr = invoice.get_period_label("fr")
    period_ar = invoice.get_period_label("ar")

    balance = invoice.get_balance()
    amt_fr = f"{balance:,.2f}".replace(",", " ").replace(".", ",")
    amt_ar = f"{balance:,.2f}".replace(",", " ").replace(".", ",")

    grp_fr = invoice.group.name_fr if invoice.group else "Échecs"
    grp_ar = invoice.group.name_ar if invoice.group else "الشطرنج"

    if lang == "ar":
        message = (
            f"السلام عليكم ورحمة الله السيد(ة) {p_name_ar}،\n\n"
            f"تذكير ودي بخصوص واجب اشتراك الشطرنج للتلميذ(ة) {st_name_ar} ({grp_ar}) لشهر {period_ar} : "
            f"المبلغ المتبقي هو {amt_ar} درهم.\n\n"
            f"يمكنكم تسوية الواجب بكل أريحية خلال الحصة القادمة (آخر أجل هو 15 من هذا الشهر كأقصى حد).\n\n"
            f"نتمنى لكم يوماً طيباً ومباركاً ! 🌟\n"
            f"Genius Chess Academy — جمعية الشطرنج القاسمي"
        )
    else:
        message = (
            f"Bonjour M./Mme {p_name_fr},\n\n"
            f"Petit rappel amical concernant la cotisation d'échecs de {st_name_fr} ({grp_fr}) pour le mois de {period_fr} : "
            f"reliquat de {amt_fr} DH.\n\n"
            f"Vous pouvez régler lors de la prochaine séance (dernier délai le 15 du mois au plus tard).\n\n"
            f"Belle journée à vous ! 🌟\n"
            f"Genius Chess Academy — جمعية الشطرنج القاسمي"
        )
    return message


def get_unpaid_reminder_chat_url(invoice, lang="fr"):
    """
    Génère le lien direct 'wa.me' pour ouvrir WhatsApp avec le texte de relance pré-rempli.
    """
    student = invoice.student
    parent = student.parent
    if not parent or not parent.phone:
        return ""
    wa_phone = format_phone_for_whatsapp(parent.phone)
    if not wa_phone:
        return ""
    msg = build_unpaid_reminder_message(invoice, lang=lang)
    encoded = urllib.parse.quote(msg)
    return f"https://wa.me/{wa_phone}?text={encoded}"


def get_last_reminder_info(invoice):
    """
    Vérifie si une relance WhatsApp a déjà été envoyée pour cette facture.
    Retourne (has_been_sent: bool, date_str: str).
    """
    parent = invoice.student.parent
    if not parent or not parent.user:
        return False, None

    last_notif = Notification.objects.filter(
        recipient=parent.user,
        notification_type='unpaid_whatsapp_reminder',
        title_fr__contains=f"Facture #{invoice.id}"
    ).order_by('-created_at').first()

    if last_notif:
        return True, last_notif.created_at
    return False, None


def send_single_unpaid_whatsapp_reminder(invoice, force=False):
    """
    Envoie le message de relance d'impayé au parent via la passerelle WhatsApp.
    Enregistre l'horodatage et la notification interne.
    """
    balance = invoice.get_balance()
    if balance <= Decimal('0.00'):
        return {'success': False, 'error': "Facture déjà soldée."}

    parent = invoice.student.parent
    if not parent or not parent.phone:
        return {'success': False, 'error': "Numéro de téléphone parent introuvable."}

    wa_phone = format_phone_for_whatsapp(parent.phone)
    if not wa_phone:
        return {'success': False, 'error': "Format du numéro de téléphone invalide."}

    already_sent, sent_date = get_last_reminder_info(invoice)
    if already_sent and not force:
        # Vérifier si envoyé ce mois-ci
        if sent_date and sent_date.month == date.today().month and sent_date.year == date.today().year:
            return {'success': False, 'error': "Relance déjà envoyée ce mois-ci.", 'already_sent': True}

    lang = parent.preferred_language or "fr"
    message = build_unpaid_reminder_message(invoice, lang=lang)

    # 1. Envoi via passerelle WhatsApp
    gateway_res = send_whatsapp_via_gateway(wa_phone, message)

    # 2. Notification interne pour l'historique et anti-doublon
    if parent.user:
        Notification.objects.create(
            recipient=parent.user,
            title_fr=f"⚠️ Rappel Facture #{invoice.id} ({invoice.get_period_label('fr')})",
            title_ar=f"⚠️ تذكير بالفاتورة #{invoice.id} ({invoice.get_period_label('ar')})",
            message_fr=f"Rappel de reliquat de {balance} DH pour l'élève {invoice.student.get_full_name('fr')}.",
            message_ar=f"تذكير بمبلغ متبقٍ قدره {balance} درهم لفائدة {invoice.student.get_full_name('ar')}.",
            notification_type='unpaid_whatsapp_reminder'
        )

    return {
        'success': True,
        'gateway_result': gateway_res,
        'sent_to': wa_phone,
        'invoice_id': invoice.id
    }


def send_bulk_authorized_reminders(invoice_ids):
    """
    Envoie les relances WhatsApp uniquement pour la liste des factures
    sélectionnées et autorisées par l'administrateur.
    """
    invoices = Invoice.objects.filter(
        id__in=invoice_ids,
        status__in=['unpaid', 'partial']
    ).select_related('student', 'student__parent', 'student__parent__user', 'group')

    sent_count = 0
    failed_count = 0
    errors = []

    for inv in invoices:
        res = send_single_unpaid_whatsapp_reminder(inv, force=True)
        if res.get('success'):
            sent_count += 1
        else:
            failed_count += 1
            errors.append(f"Facture #{inv.id} ({inv.student.get_full_name('fr')}): {res.get('error')}")

    return {
        'total_selected': len(invoices),
        'sent_count': sent_count,
        'failed_count': failed_count,
        'errors': errors
    }
