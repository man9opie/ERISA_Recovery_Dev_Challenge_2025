# ERISA Recovery Dev Challenge<br/>Claims Management System – Demo



A small Django + HTMX demo for reviewing medical claims.  
It includes a user table view with an HTMX detail panel, notes & flagging, and an **Admin Dashboard** showing average underpayment and claims needing review.

## Features

- **Welcome page** → choose **User** or **Admin** flows
- **User page** (`/user/`)
  - Paginated table with status pills (Paid / Under Review / Denied)
  - Click **View** to load a claim **detail panel** (HTMX partial)
  - **Add Note** (inline form, instant append)
  - Real time Research and Filters.
  - **Flag for Review** (re-flagging is prevented if already Under Review)
- **Admin dashboard** (`/dashboard/`)
  - Average underpayment across all claims
  - “Claims Needing Review” table 

## Bonus
- Admin Dashboard (able to view claims that being flag and average underpayment of the flag claims
- CSV Re-upload (support CSV overwrite or append new datas)
## Tech Stack

**Backend**
- **Python** 3.10+ (tested on 3.12)
- **Django** 4.2 (Django ORM, Django Templates)
- **SQLite** (dev database, bundled with Python)
- **django.contrib.humanize** for number formatting (`intcomma`, etc.)

**Frontend**
- **HTMX** 1.9+ — lightweight AJAX/HTML-over-the-wire (`hx-get`, `hx-post`, `hx-target`, `hx-swap`)
- **Alpine.js** 3 — tiny reactive bits for toggles/modals/forms (`x-data`, `x-show`, `$dispatch`)
- **Vanilla CSS** + inline SVG icons (styles live in `base.html`)

**Pages & Partials (Server-rendered)**
- Pages: `welcome.html`, `index.html` (user table), `admin_dashboard.html`
- Partials (HTMX targets):
  - `_claim_table.html` — paginated claims table
  - `_claim_detail_panel.html` / `_detail_panel.html` — claim detail card
  - `_notes_card.html` — notes & add-note form
  - `_flag_button.html` — flag-for-review button
  - `_confirm_review.html`, `_already_review.html` — modal/inline dialogs

**Architecture**
- Server-rendered HTML with progressive enhancement
- HTMX swaps for detail panel, notes, and flagging (no SPA framework)
- Pagination via Django QuerySets

## Requirements
- Python **3.10+** (3.12 tested)
- pip / venv
- SQLite (bundled with Python)

## Quickstart

# 1) Clone
```bash
git clone https://github.com/man9opie/ERISA_Recovery_Dev_Challenge_2025.git
cd ERISA_Recovery_Dev_Challenge_2025
```
# 2) Virtualenv
```bash
python -m venv .venv
# Windows:
.venv\Scripts\activate
# macOS/Linux:
# source .venv/bin/activate
```

# 3) Install deps
```bash
pip install -r requirements.txt
```
# 4) Migrate DB
```bash
python manage.py migrate
```
# 5) Load datas(or append new datas)
```bash
python manage.py load_claims data/claims.csv --delimiter '|'
python manage.py load_details data/claim_detail.csv --delimiter '|' 
```

# 5.5) If you want to overwrite the datas
```bash
python manage.py shell -c "from claims.models import Claim; Claim.objects.all().delete()"
python manage.py load_claims data/claims.csv --delimiter "|" --reset-notes all --reset-needreview all
# This will empty all the notes and set all the need review to False (bring back all the red flag
```
# 6) Run
```bash
python manage.py runserver
```
The application will run at http://127.0.0.1:8000/.

# Quick View:
<img width="1920" height="1032" alt="image" src="https://github.com/user-attachments/assets/73067393-94c6-45e7-a781-679238a00076" />
