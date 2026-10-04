import os
import sys
import gzip
import shutil
import sqlite3
import subprocess
from datetime import datetime, timedelta
from pathlib import Path

from django.conf import settings
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Sauvegarde automatique et securisee de la base de donnees GCA (SQLite/PostgreSQL) avec compression gzip et rotation des anciens backups."

    def add_arguments(self, parser):
        parser.add_argument(
            '--dest',
            type=str,
            default=str(settings.BASE_DIR / 'backups'),
            help="Dossier de destination pour les sauvegardes (defaut: BASE_DIR/backups/)",
        )
        parser.add_argument(
            '--keep-days',
            type=int,
            default=30,
            help="Nombre de jours de retention avant purge des anciennes sauvegardes (defaut: 30)",
        )
        parser.add_argument(
            '--prefix',
            type=str,
            default='gca_backup_',
            help="Prefixe du nom de fichier de sauvegarde (defaut: gca_backup_)",
        )

    def handle(self, *args, **options):
        dest_dir = Path(options['dest']).resolve()
        try:
            dest_dir.mkdir(parents=True, exist_ok=True)
            test_file = dest_dir / '.write_test'
            test_file.touch()
            test_file.unlink()
        except (PermissionError, OSError) as e:
            raise CommandError(
                f"Permission refusee dans le dossier de sauvegarde : {dest_dir}\n"
                f"Solution : executez la commande suivante sur le serveur :\n"
                f"sudo chown -R $USER:www-data {dest_dir} && sudo chmod -R 775 {dest_dir}"
            )

        keep_days = options['keep_days']
        prefix = options['prefix']

        now_str = datetime.now().strftime('%Y%m%d_%H%M%S')
        db_conf = settings.DATABASES.get('default', {})
        engine = db_conf.get('ENGINE', '')

        self.stdout.write(self.style.NOTICE(f"[START] Demarrage de la sauvegarde de la base de donnees ({engine})..."))

        if 'sqlite3' in engine:
            backup_gz_path = self._backup_sqlite(db_conf, dest_dir, prefix, now_str)
        elif 'postgresql' in engine:
            backup_gz_path = self._backup_postgresql(db_conf, dest_dir, prefix, now_str)
        else:
            backup_gz_path = self._backup_dumpdata(dest_dir, prefix, now_str)

        # Rapport de sauvegarde
        size_bytes = backup_gz_path.stat().st_size
        size_kb = size_bytes / 1024
        size_mb = size_kb / 1024
        size_display = f"{size_mb:.2f} Mo" if size_mb >= 1 else f"{size_kb:.1f} Ko"

        self.stdout.write(self.style.SUCCESS(
            f"[OK] Sauvegarde effectuee avec succes !\n"
            f"     Fichier : {backup_gz_path.resolve()}\n"
            f"     Taille  : {size_display}"
        ))

        # Nettoyage et rotation des anciens backups
        self._rotate_backups(dest_dir, prefix, keep_days)

    def _backup_sqlite(self, db_conf, dest_dir, prefix, now_str):
        """Sauvegarde SQLite en direct via l'API sqlite3.backup() sans verrouillage bloquant."""
        db_raw_name = str(db_conf.get('NAME', settings.BASE_DIR / 'db.sqlite3'))
        
        # Gestion des bases SQLite en mémoire (ex: suite de tests pytest)
        if ':memory:' in db_raw_name or 'memorydb' in db_raw_name:
            self.stdout.write(self.style.WARNING("Base de donnees SQLite en memoire detectee, utilisation de dumpdata Django..."))
            return self._backup_dumpdata(dest_dir, prefix, now_str)

        db_path = Path(db_raw_name)
        if not db_path.exists():
            self.stdout.write(self.style.WARNING(f"Fichier SQLite physique introuvable ({db_path}), fallback dumpdata Django..."))
            return self._backup_dumpdata(dest_dir, prefix, now_str)

        temp_db = dest_dir / f"{prefix}{now_str}.tmp.sqlite3"
        final_gz = dest_dir / f"{prefix}{now_str}.sqlite3.gz"

        try:
            # 1. Utilisation de l'API de backup en direct de sqlite3 (integrite garantie)
            src_conn = sqlite3.connect(str(db_path))
            dst_conn = sqlite3.connect(str(temp_db))
            with dst_conn:
                src_conn.backup(dst_conn)
            dst_conn.close()
            src_conn.close()

            # 2. Compression gzip du fichier
            with open(temp_db, 'rb') as f_in:
                with gzip.open(final_gz, 'wb', compresslevel=9) as f_out:
                    shutil.copyfileobj(f_in, f_out)

            return final_gz
        finally:
            if temp_db.exists():
                try:
                    temp_db.unlink()
                except Exception:
                    pass

    def _backup_postgresql(self, db_conf, dest_dir, prefix, now_str):
        """Sauvegarde PostgreSQL via pg_dump avec compression gzip."""
        db_name = db_conf.get('NAME', '')
        user = db_conf.get('USER', '')
        host = db_conf.get('HOST', 'localhost')
        port = str(db_conf.get('PORT', '5432'))
        password = db_conf.get('PASSWORD', '')

        final_gz = dest_dir / f"{prefix}{now_str}.sql.gz"
        env = os.environ.copy()
        if password:
            env['PGPASSWORD'] = password

        cmd = ['pg_dump', '-h', host, '-p', port, '-U', user, db_name]

        try:
            with open(final_gz, 'wb') as f_out:
                p_dump = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env)
                p_gzip = subprocess.Popen(['gzip', '-9'], stdin=p_dump.stdout, stdout=f_out)
                p_dump.stdout.close()
                p_gzip.communicate()
                stderr = p_dump.communicate()[1]

                if p_dump.returncode != 0:
                    raise CommandError(f"Erreur pg_dump : {stderr.decode('utf-8', errors='ignore')}")

            return final_gz
        except FileNotFoundError:
            self.stdout.write(self.style.WARNING("pg_dump non trouve dans le PATH, fallback sur dumpdata Django..."))
            return self._backup_dumpdata(dest_dir, prefix, now_str)

    def _backup_dumpdata(self, dest_dir, prefix, now_str):
        """Fallback universel via la commande dumpdata de Django compressee en gzip."""
        final_gz = dest_dir / f"{prefix}{now_str}.json.gz"
        temp_json = dest_dir / f"{prefix}{now_str}.tmp.json"

        try:
            with open(temp_json, 'w', encoding='utf-8') as f:
                call_command('dumpdata', '--exclude', 'contenttypes', '--exclude', 'auth.permission', stdout=f)

            with open(temp_json, 'rb') as f_in:
                with gzip.open(final_gz, 'wb', compresslevel=9) as f_out:
                    shutil.copyfileobj(f_in, f_out)

            return final_gz
        finally:
            if temp_json.exists():
                try:
                    temp_json.unlink()
                except Exception:
                    pass

    def _rotate_backups(self, dest_dir, prefix, keep_days):
        """Purge automatique des sauvegardes de plus de `keep_days` jours."""
        cutoff_date = datetime.now() - timedelta(days=keep_days)
        deleted_count = 0

        for file_path in dest_dir.glob(f"{prefix}*"):
            if not file_path.is_file():
                continue

            try:
                mtime = datetime.fromtimestamp(file_path.stat().st_mtime)
                if mtime < cutoff_date:
                    file_path.unlink()
                    deleted_count += 1
                    self.stdout.write(f"   [PURGE] Suppression de l'ancienne sauvegarde expiree : {file_path.name}")
            except Exception as e:
                self.stdout.write(self.style.WARNING(f"   [WARN] Impossible de supprimer {file_path.name}: {e}"))

        if deleted_count > 0:
            self.stdout.write(self.style.NOTICE(f"[CLEANUP] Rotation terminee : {deleted_count} ancienne(s) sauvegarde(s) purgee(s) (> {keep_days} jours)."))
        else:
            self.stdout.write(f"[INFO] Aucune sauvegarde anterieure a {keep_days} jours a purger.")
