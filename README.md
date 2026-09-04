# GENIUS CHESS ACADEMY (GCA 2026)
### Système de Gestion Pédagogique et Financière — Architecture Bilingue Native (FR / AR)

Ce projet implémente l'intégralité des exigences de la **Spécification 47 : SUPPORT BILINGUE OBLIGATOIRE — FRANÇAIS / ARABE**.

---

## 🌟 Points Forts du Système Bilingue

1. **Sélecteur de Langue Immédiat (47.1)** :
   - 🇫🇷 **Français** (LTR) / 🇲🇦 **العربية** (RTL).
   - Bascule immédiate sans perte d'état.
   - Mémorisation du choix par utilisateur (`User.preferred_language`), en session et en cookie.
   - Raccourci clavier rapide : `Alt + L`.

2. **Interface Bilingue Complète (47.2 & 47.3)** :
   - Traduction intégrale de tous les menus, tableaux, formulaires, alertes, cartes KPI et modales.
   - Vocabulaire administratif et pédagogique marocain officiel :
     - Élèves ⇄ الطلاب
     - Formateurs ⇄ المدربون
     - Parents ⇄ أولياء الأمور
     - Planning ⇄ البرنامج
     - Présences ⇄ الحضور
     - Paiements ⇄ المدفوعات
     - Impayés ⇄ المستحقات
     - Reçus ⇄ الإيصالات
     - Espace Parent ⇄ فضاء ولي الأمر
     - Mes enfants ⇄ أبنائي

3. **Support RTL Complet (47.4 & 47.5)** :
   - Balise HTML adaptative : `<html lang="ar" dir="rtl">` / `<html lang="fr" dir="ltr">`.
   - Inversion directionnelle automatique des grilles, alignements de texte, bordures et icônes.
   - Polices arabes intégrées localement : **Cairo**, **Amiri** et **Tajawal**.

4. **Contenu Dynamique Bilingue (47.6)** :
   - Base de données unique UTF-8 supportant le français et l'arabe simultanément (`name_fr`, `name_ar`, etc.).
   - Activités : *Robotique* / *الروبوتيك*, *Échecs* / *الشطرنج*, *Calcul Mental* / *الحساب الذهني*.
   - Salles : *Salle Kasparov* / *قاعة كاسباروف*, *Salle Al-Khawarizmi* / *قاعة الخوارزمي*.

5. **Générateur de Reçus PDF Bilingues (47.7 & 47.19)** :
   - Version Française (LTR, montants en `DH`).
   - Version Arabe (RTL, montants en `درهم`, lettres arabes liées par `arabic_reshaper` et `python-bidi`).
   - Version Bilingue (double en-tête et libellés bilingues).
   - Cachet officiel Genius Chess Academy, signature et horodatage.

6. **Planning & Formats Locaux (47.8, 47.17, 47.18)** :
   - Jours de la semaine localisés (Lundi..Dimanche ⇄ الاثنين..الأحد).
   - Mois localisés (ex: *03 septembre 2026* ⇄ *03 شتنبر 2026*).
   - Montants réels en `Decimal` affichés sous forme *100,00 DH* / *100,00 درهم*.

7. **Espace Parent Dédié (47.9)** :
   - Vue famille complète avec liste des enfants (أبنائي), planning, suivi des présences, historique des paiements et téléchargement des reçus.
   - Sélecteur de langue accessible directement depuis l'espace parent.

8. **Relances Automatiques du 10 du Mois (47.10 & 47.11)** :
   - Détection des cotisations impayées ou partielles.
   - Envoi de la notification dans la langue exacte choisie par le parent (jamais de français envoyé à un parent ayant choisi l'arabe).

9. **Recherche Bilingue & Tolérance Unicode (47.13 & 47.14)** :
   - Recherche insensible aux accents en français (`Élève` ⇄ `eleve`).
   - Recherche normalisée en arabe (`أ / إ / آ / ا`, `ة / ه`, `ى / ي`).
   - Aucun caractère corrompu (`???`).

10. **Export Excel Bilingue (47.15)** :
    - Fichiers `.xlsx` OpenPyXL avec encodage UTF-8 parfait.
    - Vue feuille de calcul RTL pour la version arabe (`rightToLeft = True`).
    - Support des noms mixtes simultanés (ex: `Mohamed العلوي`).

---

## 🚀 Démarrage Rapide

### 1. Lancer les Tests Automatisés
```bash
python -m pytest -v
```
Les 10 tests automatisés valident la complétude des dictionnaires, la bidirectionnalité, les formats, les PDF, les exports Excel, la recherche et les vues.

### 2. Démarrer le Serveur Web
```bash
python manage.py runserver
```
Accéder à l'application dans votre navigateur :
👉 **http://127.0.0.1:8000/**

### 3. Comptes d'Accès
- **Administrateur** (accès complet aux fonctionnalités) :
  - Identifiant : `admin`
  - Mot de passe : `CGAESA65`
- **Parent (Arabe)** : `karim_alaoui` / `Parent@2026`
- **Parent (Français)** : `fatima_benani` / `Parent@2026`
