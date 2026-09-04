#!/bin/bash
# ==============================================================================
# Script de Déploiement Automatique Clé en Main - Genius Chess Academy (GCA 2026)
# Domaine cible : geniuschess.ma
# ==============================================================================
set -e

echo "=========================================================="
echo "♟️ DÉPLOIEMENT GENIUS CHESS ACADEMY (https://geniuschess.ma)"
echo "=========================================================="

DOMAIN="geniuschess.ma"
PROJECT_DIR="/var/www/geniuschess"
VENV_DIR="$PROJECT_DIR/venv"

# 1. Mise à jour du système et installation des paquets requis
echo "📦 1/6. Installation des dépendances système (Python, Nginx, Certbot)..."
sudo apt-get update -y
sudo apt-get install -y python3 python3-pip python3-venv nginx certbot python3-certbot-nginx unzip curl libgl1

# 2. Préparation du dossier de l'application
echo "📁 2/6. Configuration des dossiers de l'application..."
sudo mkdir -p $PROJECT_DIR
sudo chown -R $USER:$USER $PROJECT_DIR

# Décompression si une archive deploy_gca_package.zip est présente dans le dossier home
if [ -f ~/deploy_gca_package.zip ]; then
    echo "📦 Décompression de l'archive de l'application..."
    unzip -o ~/deploy_gca_package.zip -d $PROJECT_DIR
fi

# 3. Création de l'environnement virtuel Python
echo "🐍 3/6. Création de l'environnement virtuel et installation des dépendances..."
python3 -m venv $VENV_DIR
$VENV_DIR/bin/pip install --upgrade pip
if [ -f "$PROJECT_DIR/requirements.txt" ]; then
    $VENV_DIR/bin/pip install -r $PROJECT_DIR/requirements.txt
fi

# 4. Migrations et collecte des fichiers statiques
echo "⚙️ 4/6. Application des migrations et collecte des fichiers statiques..."
cd $PROJECT_DIR
$VENV_DIR/bin/python manage.py collectstatic --noinput

# 5. Création du service Systemd pour Gunicorn (démarrage automatique 24h/24)
echo "🚀 5/6. Configuration du service systemd Gunicorn..."
sudo tee /etc/systemd/system/gca.service > /dev/null <<EOF
[Unit]
Description=Gunicorn daemon for Genius Chess Academy
After=network.target

[Service]
User=$USER
Group=www-data
WorkingDirectory=$PROJECT_DIR
ExecStart=$VENV_DIR/bin/gunicorn --workers 3 --bind 127.0.0.1:8000 gca_config.wsgi:application
Restart=always

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable gca
sudo systemctl restart gca

# 6. Configuration du serveur Web Nginx
echo "🌐 6/6. Configuration de Nginx pour $DOMAIN..."
sudo tee /etc/nginx/sites-available/geniuschess > /dev/null <<EOF
server {
    server_name $DOMAIN www.$DOMAIN;

    location = /favicon.ico { 
        access_log off; 
        log_not_found off; 
        alias $PROJECT_DIR/static/img/favicon.png;
    }

    location /static/ {
        alias $PROJECT_DIR/static/;
        expires 30d;
    }

    location / {
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_pass http://127.0.0.1:8000;
    }
}
EOF

sudo ln -sf /etc/nginx/sites-available/geniuschess /etc/nginx/sites-enabled/
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t
sudo systemctl restart nginx

echo ""
echo "=========================================================="
echo "✅ APPLICATION DÉPLOYÉE ET OPÉRATIONNELLE SUR NGINX !"
echo "=========================================================="
echo "Pour activer le cadenas vert HTTPS gratuit (SSL), exécutez :"
echo "sudo certbot --nginx -d $DOMAIN -d www.$DOMAIN"
echo "=========================================================="
