import os
import gzip
import time
import sqlite3
from pathlib import Path
import pytest
from django.core.management import call_command
from academy.management.commands.backup_database import Command as BackupCommand


@pytest.mark.django_db
def test_backup_database_command_memory_and_rotation(tmp_path):
    """
    Teste la commande backup_database sous environnement de test (mémoire/dumpdata)
    et valide la rotation automatique des anciennes sauvegardes.
    """
    backup_dir = tmp_path / "test_backups"
    backup_dir.mkdir(parents=True, exist_ok=True)

    # 1. Création d'un fichier ancien simulé (> 30 jours)
    old_file = backup_dir / "gca_backup_20200101_000000.sqlite3.gz"
    old_file.touch()
    old_timestamp = time.time() - (35 * 86400)
    os.utime(str(old_file), (old_timestamp, old_timestamp))
    assert old_file.exists()

    # 2. Exécution de la commande
    call_command('backup_database', dest=str(backup_dir), keep_days=30)

    # 3. Vérifier que l'ancien fichier a été purgé
    assert not old_file.exists(), "L'ancienne sauvegarde aurait dû être purgée par la rotation."

    # 4. Vérifier qu'un nouveau backup valide a été créé (.json.gz ou .sqlite3.gz)
    created_backups = list(backup_dir.glob("gca_backup_*.gz"))
    assert len(created_backups) == 1, f"Un seul backup récent attendu, trouvé : {created_backups}"

    new_backup = created_backups[0]
    assert new_backup.stat().st_size > 0

    # 5. Vérifier que le fichier est un gzip valide et décompressible
    with gzip.open(new_backup, 'rb') as gz_f:
        content = gz_f.read(100)
        assert len(content) > 0


def test_backup_sqlite_physical_file(tmp_path):
    """
    Teste spécifiquement _backup_sqlite avec un vrai fichier SQLite
    pour vérifier l'API de backup en direct et le header officiel SQLite 3.
    """
    # 1. Créer une vraie petite base SQLite physique
    fake_db = tmp_path / "physical_test.sqlite3"
    conn = sqlite3.connect(str(fake_db))
    conn.execute("CREATE TABLE test_table (id INTEGER PRIMARY KEY, name TEXT)")
    conn.execute("INSERT INTO test_table (name) VALUES ('Genius Chess Academy')")
    conn.commit()
    conn.close()

    dest_dir = tmp_path / "output_backups"
    dest_dir.mkdir(parents=True, exist_ok=True)

    cmd = BackupCommand()
    db_conf = {'NAME': str(fake_db)}
    backup_gz = cmd._backup_sqlite(db_conf, dest_dir, "gca_test_", "20261004_120000")

    assert backup_gz.exists()
    assert backup_gz.name == "gca_test_20261004_120000.sqlite3.gz"

    # Vérification du header SQLite 3
    with gzip.open(backup_gz, 'rb') as f:
        header = f.read(16)
        assert header.startswith(b'SQLite format 3')
