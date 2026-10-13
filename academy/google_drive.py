"""
Service d'intégration Google Drive pour Genius Chess Academy (GCA).
Gère l'upload, la récupération de métadonnées, les permissions et la suppression
de fichiers vers le stockage Google One (5 To).
Garantit ZÉRO stockage persistant sur le disque dur du serveur VPS.
"""

import io
import os
import logging
from django.conf import settings

logger = logging.getLogger(__name__)

# Scopes nécessaires pour gérer les fichiers Google Drive
SCOPES = ['https://www.googleapis.com/auth/drive']


def get_drive_service():
    """
    Initialise et retourne le client Google Drive API authentifié
    via le compte de service Google Cloud.
    """
    try:
        from google.oauth2 import service_account
        from googleapiclient.discovery import build
    except ImportError as e:
        logger.error(f"Bibliothèques Google manquantes : {e}")
        raise RuntimeError("Les packages 'google-api-python-client' et 'google-auth' ne sont pas installés.")

    credentials_path = getattr(settings, 'GOOGLE_DRIVE_CREDENTIALS_FILE', None)
    if not credentials_path or not os.path.exists(credentials_path):
        raise FileNotFoundError(f"Fichier d'identifiants Google introuvable : {credentials_path}")

    creds = service_account.Credentials.from_service_account_file(
        credentials_path,
        scopes=SCOPES
    )
    service = build('drive', 'v3', credentials=creds, cache_discovery=False)
    return service


def upload_file_to_drive(file_obj, filename, mime_type=None, folder_id=None):
    """
    Téléverse un fichier (Django UploadedFile ou objet fichier en mémoire)
    directement dans le dossier Google Drive ciblé (5 To).
    
    Paramètres :
        - file_obj : fichier Django UploadedFile ou BytesIO / objet avec read()
        - filename : nom du fichier à enregistrer sur Google Drive
        - mime_type : type MIME (ex: 'image/jpeg', 'video/mp4')
        - folder_id : ID du dossier cible (défaut : settings.GOOGLE_DRIVE_FOLDER_ID)
        
    Retourne :
        dict avec :
            - file_id : ID unique Google Drive
            - web_view_link : Lien de consultation web
            - thumbnail_link : Lien miniature
            - size_mb : Taille en Mégaoctets
    """
    from googleapiclient.http import MediaIoBaseUpload

    target_folder_id = folder_id or getattr(settings, 'GOOGLE_DRIVE_FOLDER_ID', '1MwD-jVDclNwRSjtFr9UbnUWOM-TvwKTh')
    service = get_drive_service()

    # Déterminer la taille
    file_size_bytes = 0
    if hasattr(file_obj, 'size'):
        file_size_bytes = file_obj.size
    elif hasattr(file_obj, 'seek') and hasattr(file_obj, 'tell'):
        cur = file_obj.tell()
        file_obj.seek(0, io.SEEK_END)
        file_size_bytes = file_obj.tell()
        file_obj.seek(cur)

    # Réinitialiser la tête de lecture
    if hasattr(file_obj, 'seek'):
        file_obj.seek(0)

    # Métadonnées du fichier Drive
    file_metadata = {
        'name': filename,
        'parents': [target_folder_id]
    }

    # Création du flux d'upload (resumable pour les vidéos et images lourdes)
    media = MediaIoBaseUpload(
        file_obj,
        mimetype=mime_type or 'application/octet-stream',
        chunksize=1024 * 1024 * 5,  # Chunks de 5 Mo
        resumable=True
    )

    # Exécution de l'upload
    request = service.files().create(
        body=file_metadata,
        media_body=media,
        fields='id, name, webViewLink, webContentLink, thumbnailLink, size'
    )

    response = None
    while response is None:
        status, response = request.next_chunk()
        if status:
            logger.info(f"Progression Upload '{filename}': {int(status.progress() * 100)}%")

    file_id = response.get('id')
    logger.info(f"Upload réussi pour '{filename}' - Drive ID: {file_id}")

    # Rendre le fichier accessible en lecture à toute personne ayant le lien
    try:
        service.permissions().create(
            fileId=file_id,
            body={'role': 'reader', 'type': 'anyone'},
            fields='id'
        ).execute()
    except Exception as perm_err:
        logger.warning(f"Impossible d'assigner la permission publique sur {file_id}: {perm_err}")

    size_mb = round(file_size_bytes / (1024 * 1024), 2) if file_size_bytes else 0.0

    return {
        'file_id': file_id,
        'web_view_link': response.get('webViewLink', f"https://drive.google.com/file/d/{file_id}/view"),
        'thumbnail_link': response.get('thumbnailLink', f"https://lh3.googleusercontent.com/d/{file_id}=s800"),
        'size_mb': size_mb,
    }


def delete_file_from_drive(file_id):
    """Supprime un fichier sur Google Drive par son file_id."""
    if not file_id:
        return False
    try:
        service = get_drive_service()
        service.files().delete(fileId=file_id).execute()
        logger.info(f"Fichier supprimé de Google Drive: {file_id}")
        return True
    except Exception as e:
        logger.error(f"Erreur lors de la suppression Drive {file_id}: {e}")
        return False


def test_drive_connection():
    """
    Vérifie la connexion avec l'API Google Drive et l'accès au dossier racine (5 To).
    Retourne (bool_success, message_info).
    """
    try:
        service = get_drive_service()
        target_folder_id = getattr(settings, 'GOOGLE_DRIVE_FOLDER_ID', '1MwD-jVDclNwRSjtFr9UbnUWOM-TvwKTh')
        
        # Test 1 : Récupérer les infos du dossier racine
        folder = service.files().get(
            fileId=target_folder_id,
            fields='id, name, mimeType, capabilities'
        ).execute()
        
        name = folder.get('name', 'Inconnu')
        can_add_children = folder.get('capabilities', {}).get('canAddChildren', False)
        
        return True, f"Connexion Google Drive OK. Dossier: '{name}' (ID: {target_folder_id}). Droits d'écriture: {'Oui' if can_add_children else 'Non'}"
    except Exception as e:
        return False, f"Échec de connexion Google Drive: {str(e)}"
