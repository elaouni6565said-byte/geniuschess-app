import os

os.makedirs('static/css', exist_ok=True)

css = """/* ==========================================================================
   GENIUS CHESS ACADEMY (GCA 2026) - BILINGUAL LTR / RTL DESIGN SYSTEM
   Couleurs officielles:
   - Navy:   #001B57
   - Blue:   #0077CE
   - Orange: #FF6E00
   ========================================================================== */

@import url('https://fonts.googleapis.com/css2?family=Cairo:wght@400;600;700;800&family=Inter:wght@400;500;600;700&display=swap');

:root {
  --primary-navy: #001B57;
  --primary-blue: #0077CE;
  --accent-orange: #FF6E00;
  --bg-main: #F8FAFC;
  --bg-card: #FFFFFF;
  --text-main: #0F172A;
  --text-muted: #64748B;
  --border-color: #E2E8F0;
  --success: #10B981;
  --warning: #F59E0B;
  --danger: #EF4444;
  --shadow-sm: 0 1px 2px 0 rgb(0 0 0 / 0.05);
  --shadow-md: 0 4px 6px -1px rgb(0 0 0 / 0.1), 0 2px 4px -2px rgb(0 0 0 / 0.1);
  --shadow-lg: 0 10px 15px -3px rgb(0 0 0 / 0.1), 0 4px 6px -4px rgb(0 0 0 / 0.1);
  --radius-sm: 6px;
  --radius-md: 10px;
  --radius-lg: 16px;
}

* {
  box-sizing: border-box;
  margin: 0;
  padding: 0;
}

body {
  font-family: 'Inter', system-ui, -apple-system, sans-serif;
  background-color: var(--bg-main);
  color: var(--text-main);
  line-height: 1.5;
  min-height: 100vh;
  display: flex;
  flex-direction: column;
}

/* RTL Typography & Layout Overrides */
html[dir="rtl"] body {
  font-family: 'Cairo', 'Segoe UI', Tahoma, sans-serif;
  text-align: right;
}

a {
  color: var(--primary-blue);
  text-decoration: none;
  transition: color 0.15s ease;
}
a:hover {
  color: var(--primary-navy);
}

/* ==========================================================================
   NAVBAR & HEADER
   ========================================================================== */
.gca-navbar {
  background: var(--primary-navy);
  color: #FFFFFF;
  padding: 0.75rem 1.5rem;
  display: flex;
  align-items: center;
  justify-content: space-between;
  box-shadow: var(--shadow-md);
  position: sticky;
  top: 0;
  z-index: 100;
}

.brand-section {
  display: flex;
  align-items: center;
  gap: 1rem;
}

.brand-logo-badge {
  background: var(--accent-orange);
  color: white;
  width: 44px;
  height: 44px;
  border-radius: var(--radius-md);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 1.5rem;
  font-weight: 800;
  box-shadow: var(--shadow-sm);
}

.brand-titles h1 {
  font-size: 1.25rem;
  font-weight: 700;
  letter-spacing: -0.02em;
  color: #FFFFFF;
  line-height: 1.2;
}
.brand-titles span {
  font-size: 0.75rem;
  color: #93C5FD;
  display: block;
}

.nav-links {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  list-style: none;
}

.nav-item a {
  color: #E2E8F0;
  padding: 0.5rem 0.85rem;
  border-radius: var(--radius-sm);
  font-size: 0.9rem;
  font-weight: 500;
  display: flex;
  align-items: center;
  gap: 0.4rem;
  transition: all 0.2s;
}

.nav-item a:hover,
.nav-item.active a {
  background: rgba(255, 255, 255, 0.12);
  color: #FFFFFF;
}

.nav-item.active a {
  border-bottom: 2.5px solid var(--accent-orange);
}

/* Language Switcher Widget (47.1) */
.lang-switcher-widget {
  display: flex;
  align-items: center;
  background: rgba(255, 255, 255, 0.15);
  padding: 3px;
  border-radius: 9999px;
  border: 1px solid rgba(255, 255, 255, 0.2);
}

.lang-btn {
  display: flex;
  align-items: center;
  gap: 0.35rem;
  padding: 0.35rem 0.75rem;
  font-size: 0.85rem;
  border-radius: 9999px;
  color: #CBD5E1;
  font-weight: 600;
  transition: all 0.2s ease;
}

.lang-btn:hover {
  color: #FFFFFF;
}

.lang-btn.active {
  background: var(--accent-orange);
  color: #FFFFFF;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.2);
}

/* ==========================================================================
   LAYOUT CONTAINER
   ========================================================================== */
.main-wrapper {
  flex: 1;
  max-width: 1320px;
  width: 100%;
  margin: 1.5rem auto;
  padding: 0 1.5rem;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 1.5rem;
  gap: 1rem;
  flex-wrap: wrap;
}

.page-header-titles h2 {
  font-size: 1.65rem;
  color: var(--primary-navy);
  font-weight: 700;
}
.page-header-titles p {
  color: var(--text-muted);
  font-size: 0.95rem;
}

.page-actions {
  display: flex;
  gap: 0.75rem;
  align-items: center;
}

/* ==========================================================================
   BUTTONS
   ========================================================================== */
.btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 0.5rem;
  padding: 0.6rem 1.15rem;
  font-size: 0.9rem;
  font-weight: 600;
  border-radius: var(--radius-sm);
  border: none;
  cursor: pointer;
  transition: all 0.15s ease;
  text-decoration: none;
}

.btn-primary {
  background: var(--primary-navy);
  color: #FFFFFF;
}
.btn-primary:hover {
  background: #00123D;
  color: #FFFFFF;
}

.btn-secondary {
  background: var(--primary-blue);
  color: #FFFFFF;
}
.btn-secondary:hover {
  background: #0060A8;
  color: #FFFFFF;
}

.btn-accent {
  background: var(--accent-orange);
  color: #FFFFFF;
}
.btn-accent:hover {
  background: #E05F00;
  color: #FFFFFF;
}

.btn-outline {
  background: transparent;
  border: 1.5px solid var(--border-color);
  color: var(--text-main);
}
.btn-outline:hover {
  background: #F1F5F9;
  border-color: #CBD5E1;
}

.btn-sm {
  padding: 0.35rem 0.65rem;
  font-size: 0.8rem;
}

/* Directional Icon Inversion (47.4) */
html[dir="rtl"] .icon-dir {
  transform: scaleX(-1);
}

/* ==========================================================================
   CARDS & GRID
   ========================================================================== */
.grid-kpi {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
  gap: 1.25rem;
  margin-bottom: 2rem;
}

.kpi-card {
  background: var(--bg-card);
  padding: 1.25rem;
  border-radius: var(--radius-md);
  border: 1px solid var(--border-color);
  box-shadow: var(--shadow-sm);
  display: flex;
  align-items: center;
  justify-content: space-between;
  transition: transform 0.2s, box-shadow 0.2s;
}

.kpi-card:hover {
  transform: translateY(-2px);
  box-shadow: var(--shadow-md);
}

.kpi-content h4 {
  font-size: 0.85rem;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--text-muted);
  margin-bottom: 0.35rem;
}

.kpi-content .kpi-value {
  font-size: 1.75rem;
  font-weight: 800;
  color: var(--primary-navy);
}

.kpi-icon {
  width: 48px;
  height: 48px;
  border-radius: var(--radius-sm);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 1.4rem;
}

.kpi-icon.blue   { background: #EFF6FF; color: var(--primary-blue); }
.kpi-icon.navy   { background: #EEF2FF; color: var(--primary-navy); }
.kpi-icon.orange { background: #FFF7ED; color: var(--accent-orange); }
.kpi-icon.green  { background: #ECFDF5; color: var(--success); }
.kpi-icon.red    { background: #FEF2F2; color: var(--danger); }

.card {
  background: var(--bg-card);
  border-radius: var(--radius-md);
  border: 1px solid var(--border-color);
  box-shadow: var(--shadow-sm);
  padding: 1.5rem;
  margin-bottom: 1.5rem;
}

.card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding-bottom: 1rem;
  margin-bottom: 1.25rem;
  border-bottom: 1px solid var(--border-color);
}

.card-title {
  font-size: 1.15rem;
  font-weight: 700;
  color: var(--primary-navy);
}

/* ==========================================================================
   TABLES (BILINGUAL LTR / RTL)
   ========================================================================== */
.table-responsive {
  width: 100%;
  overflow-x: auto;
}

.gca-table {
  width: 100%;
  border-collapse: separate;
  border-spacing: 0;
  font-size: 0.9rem;
}

.gca-table th {
  background: #F1F5F9;
  color: var(--primary-navy);
  font-weight: 700;
  padding: 0.75rem 1rem;
  border-bottom: 2px solid var(--border-color);
  text-align: left;
}

html[dir="rtl"] .gca-table th {
  text-align: right;
}

.gca-table td {
  padding: 0.85rem 1rem;
  border-bottom: 1px solid var(--border-color);
  color: var(--text-main);
  vertical-align: middle;
}

.gca-table tr:hover td {
  background-color: #F8FAFC;
}

/* Status Badges */
.badge {
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
  padding: 0.25rem 0.65rem;
  font-size: 0.75rem;
  font-weight: 700;
  border-radius: 9999px;
}

.badge-paid {
  background: #DEF7EC;
  color: #03543F;
}
.badge-partial {
  background: #FEF08A;
  color: #854D0E;
}
.badge-unpaid {
  background: #FDE8E8;
  color: #9B1C1C;
}

/* ==========================================================================
   SEARCH & FILTERS BAR
   ========================================================================== */
.filter-bar {
  display: flex;
  gap: 1rem;
  align-items: center;
  background: var(--bg-card);
  padding: 1rem 1.25rem;
  border-radius: var(--radius-md);
  border: 1px solid var(--border-color);
  margin-bottom: 1.5rem;
  flex-wrap: wrap;
}

.search-input-wrapper {
  position: relative;
  flex: 1;
  min-width: 250px;
}

.search-input {
  width: 100%;
  padding: 0.6rem 1rem;
  border-radius: var(--radius-sm);
  border: 1.5px solid var(--border-color);
  font-size: 0.9rem;
  outline: none;
  font-family: inherit;
}

.search-input:focus {
  border-color: var(--primary-blue);
  box-shadow: 0 0 0 3px rgba(0, 119, 206, 0.15);
}

.filter-select {
  padding: 0.6rem 1rem;
  border-radius: var(--radius-sm);
  border: 1.5px solid var(--border-color);
  font-size: 0.9rem;
  background: white;
  font-family: inherit;
  outline: none;
}

/* ==========================================================================
   MESSAGES & ALERTS
   ========================================================================== */
.alert-banner {
  padding: 1rem 1.25rem;
  border-radius: var(--radius-sm);
  margin-bottom: 1.5rem;
  font-size: 0.95rem;
  font-weight: 500;
  display: flex;
  align-items: center;
  gap: 0.75rem;
}
.alert-success {
  background: #DEF7EC;
  border: 1px solid #31C48D;
  color: #03543F;
}
.alert-info {
  background: #E1EFFE;
  border: 1px solid #76A9FA;
  color: #1E429F;
}
.alert-warning {
  background: #FDF6B2;
  border: 1px solid #FACA15;
  color: #723B13;
}

/* ==========================================================================
   FOOTER
   ========================================================================== */
.gca-footer {
  background: #FFFFFF;
  border-top: 1px solid var(--border-color);
  padding: 1.5rem;
  text-align: center;
  color: var(--text-muted);
  font-size: 0.85rem;
  margin-top: auto;
}
"""

with open('static/css/gca-style.css', 'w', encoding='utf-8') as f:
    f.write(css)

print('Created static/css/gca-style.css')
