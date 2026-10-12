import json
import logging
import subprocess
import time as pytime
import urllib.request
import urllib.error
from datetime import date, datetime
from django.conf import settings
from django.utils import timezone
from academy.models import SessionSchedule, Student, Parent, WhatsAppDispatchLog
from academy.whatsapp_reminders import (
    get_daily_sessions_reminders,
    send_whatsapp_via_gateway,
    format_phone_for_whatsapp,
    is_day_cancelled,
)

logger = logging.getLogger('gca.watchdog')
ADMIN_PHONE = getattr(settings, 'ADMIN_WHATSAPP_PHONE', '212606424142')


def check_waha_health():
    """
    Vérifie l'état de santé de la passerelle WhatsApp WAHA (port 3000).
    Retourne un dictionnaire avec le statut et les détails.
    """
    gateway_url = getattr(settings, 'WHATSAPP_GATEWAY_URL', 'http://127.0.0.1:3000/api/sendText')
    token = getattr(settings, 'WHATSAPP_TOKEN', '')
    session_name = getattr(settings, 'WHATSAPP_SESSION_NAME', 'default')

    base_url = gateway_url.split('/api/')[0] if '/api/' in gateway_url else 'http://127.0.0.1:3000'
    check_url = f"{base_url}/api/sessions"

    req = urllib.request.Request(check_url, headers={'User-Agent': 'GCA-Watchdog/2.0'})
    if token:
        req.add_header('X-Api-Key', token)

    try:
        with urllib.request.urlopen(req, timeout=8) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            if isinstance(data, list):
                for sess in data:
                    if sess.get('name') == session_name:
                        st = sess.get('status')
                        me = sess.get('me', {})
                        phone_id = me.get('id', '') if me else ''
                        if st == 'WORKING':
                            return {
                                'healthy': True,
                                'status': 'WORKING',
                                'phone': phone_id,
                                'detail': f"Session {session_name} connectée ({phone_id})"
                            }
                        return {
                            'healthy': False,
                            'status': st or 'UNKNOWN',
                            'phone': phone_id,
                            'detail': f"Session {session_name} en état: {st}"
                        }
            return {'healthy': True, 'status': 'ONLINE', 'detail': 'Passerelle répond'}
    except urllib.error.HTTPError as e:
        return {'healthy': False, 'status': f"HTTP_{e.code}", 'detail': f"Erreur HTTP {e.code} ({e.reason})"}
    except (urllib.error.URLError, TimeoutError) as e:
        return {'healthy': False, 'status': 'UNREACHABLE', 'detail': f"Injoignable: {e}"}
    except Exception as e:
        return {'healthy': False, 'status': 'ERROR', 'detail': str(e)}


def repair_waha_service():
    """
    Tente de réparer automatiquement la passerelle WAHA en redémarrant le conteneur Docker.
    """
    logger.warning("Watchdog : Détection d'une défaillance WAHA. Tentative de redémarrage automatique...")
    try:
        res = subprocess.run(
            ["docker", "restart", "waha"],
            capture_output=True,
            text=True,
            timeout=40
        )
        if res.returncode == 0:
            logger.info("Watchdog : Conteneur WAHA redémarré. Attente de reconnexion (12s)...")
            pytime.sleep(12)
            # Re-tester la santé
            health = check_waha_health()
            if health['healthy']:
                logger.info("Watchdog : WAHA réparé et reconnecté avec succès !")
                return {'repaired': True, 'health': health, 'detail': 'Conteneur WAHA redémarré avec succès.'}
            else:
                return {'repaired': False, 'health': health, 'detail': f"Redémarré mais statut: {health['status']}"}
        else:
            return {'repaired': False, 'error': res.stderr or 'Code retour non nul'}
    except Exception as e:
        logger.error(f"Watchdog : Erreur lors de la tentative de redémarrage Docker : {e}")
        return {'repaired': False, 'error': str(e)}


def send_admin_sos(message):
    """
    Envoie une notification d'alerte haute priorité sur le WhatsApp de l'administrateur.
    """
    if not ADMIN_PHONE:
        return False
    try:
        sos_text = f"🚨 *ALERTE WATCHDOG — Genius Chess Academy* 🚨\n\n{message}\n\n🕒 {timezone.now().strftime('%d/%m/%Y %H:%M:%S')}"
        res = send_whatsapp_via_gateway(ADMIN_PHONE, sos_text)
        return res.get('success', False)
    except Exception as e:
        logger.error(f"Erreur envoi alerte admin SOS : {e}")
        return False


def run_reminders_watchdog_loop(target_date=None, force_resend=False):
    """
    Boucle de contrôle principale et d'auto-réparation :
    1. Teste et auto-répare la passerelle WAHA si nécessaire.
    2. Parcourt toutes les séances programmées du jour.
    3. Identifie les élèves n'ayant pas encore reçu leur rappel.
    4. Envoie ou ré-essaye (jusqu'à 3 tentatives intelligentes).
    5. Journalise chaque tentative dans WhatsAppDispatchLog.
    6. Alerte l'administrateur par WhatsApp si un parent reste injoignable.
    """
    if target_date is None:
        target_date = date.today()

    report = {
        'target_date': target_date,
        'executed_at': timezone.now(),
        'waha_initial_health': None,
        'waha_repaired': False,
        'total_sessions': 0,
        'total_expected': 0,
        'already_delivered': 0,
        'newly_sent': 0,
        'failed_attempts': 0,
        'permanent_failures': 0,
        'logs_created_or_updated': 0,
        'day_cancelled': False,
        'details': [],
    }

    # 1. Contrôle & Auto-réparation Passerelle
    health = check_waha_health()
    report['waha_initial_health'] = health

    if not health['healthy']:
        repair_res = repair_waha_service()
        report['waha_repaired'] = repair_res.get('repaired', False)
        if not report['waha_repaired']:
            send_admin_sos(
                f"La passerelle WhatsApp (WAHA) est défaillante sur le serveur.\n"
                f"Détail : {health.get('detail')}\n"
                f"L'auto-réparation n'a pas pu rétablir la connexion. Une intervention manuelle est requise."
            )

    if is_day_cancelled(target_date):
        report['day_cancelled'] = True
        return report

    # 2. Collecte des rappels prévus aujourd'hui
    items = get_daily_sessions_reminders(target_date)
    report['total_expected'] = len(items)

    for it in items:
        if it.get('is_cancelled'):
            continue

        sch = it['schedule']
        st = it['student']
        parent = it['parent']
        wa_phone = it.get('whatsapp_phone')
        msg_text = it['message_text']

        if not wa_phone:
            report['permanent_failures'] += 1
            report['details'].append({
                'student': st.get_full_name('fr'),
                'status': 'error_no_phone',
                'message': 'Pas de numéro de téléphone parent.'
            })
            continue

        # Vérifier l'historique dans WhatsAppDispatchLog
        log, created = WhatsAppDispatchLog.objects.get_or_create(
            student=st,
            session_schedule=sch,
            target_date=target_date,
            message_type='session_reminder',
            defaults={
                'parent': parent,
                'phone': wa_phone,
                'message_text': msg_text,
                'status': 'pending',
                'attempt_count': 0
            }
        )

        # Si déjà envoyé avec succès et pas de forçage : on saute (protection anti-doublon absolue)
        if log.status == 'sent' and not force_resend:
            report['already_delivered'] += 1
            continue

        # Si déjà 3 échecs enregistrés : on ne harcèle pas, on alerte l'admin
        if log.attempt_count >= 3 and log.status == 'failed' and not force_resend:
            report['permanent_failures'] += 1
            continue

        # TENTATIVE D'ENVOI VIA PASSERELLE
        log.attempt_count += 1
        res = send_whatsapp_via_gateway(wa_phone, msg_text)

        if res.get('success'):
            log.status = 'sent'
            log.sent_at = timezone.now()
            log.response_payload = str(res.get('response', 'OK'))
            log.last_error = ''
            log.save()
            report['newly_sent'] += 1
            report['details'].append({
                'student': st.get_full_name('fr'),
                'phone': wa_phone,
                'status': 'success',
                'attempt': log.attempt_count
            })
        else:
            err = res.get('error', 'Erreur inconnue')
            log.last_error = str(err)
            if log.attempt_count >= 3:
                log.status = 'failed'
                report['permanent_failures'] += 1
                # Envoi alerte SOS à l'admin
                send_admin_sos(
                    f"Échec définitif du rappel de séance après 3 tentatives :\n"
                    f"👤 Élève : {st.get_full_name('fr')}\n"
                    f"📞 Parent : {parent.full_name_fr} ({wa_phone})\n"
                    f"🕒 Séance : {it['time_str']}\n"
                    f"❌ Erreur : {err}"
                )
            else:
                log.status = 'retrying'
                report['failed_attempts'] += 1

            log.save()
            report['details'].append({
                'student': st.get_full_name('fr'),
                'phone': wa_phone,
                'status': 'failed',
                'attempt': log.attempt_count,
                'error': err
            })

        pytime.sleep(1)

    return report
