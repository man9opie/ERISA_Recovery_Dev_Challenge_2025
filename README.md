# ERISA Recovery Dev Challenge<br/>Claims Management System – Demo



A small Django + HTMX demo for reviewing medical claims.  
It includes a user table view with an HTMX detail panel, notes & flagging, and an **Admin Dashboard** showing average underpayment and claims needing review.

## Features

- **Welcome page** → choose **User** or **Admin** flows
- **User page** (`/user/`)
  - Paginated table with status pills (Paid / Under Review / Denied)
  - Click **View** to load a claim **detail panel** (HTMX partial)
  - **Add Note** (inline form, instant append)
  - **Flag for Review** (confirm dialog; prevents re-flagging if already Under Review)
- **Admin dashboard** (`/dashboard/`)
  - Average underpayment across all claims
  - “Claims Needing Review” table (same visual style as user table)
  - **Flag** button disabled on admin side
- HTMX-driven partials for smooth UI without a SPA

## Bonus
- Admin Dashboard
- CSV Re-upload(support CSV overwrite or append new datas)

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
# 5) Load datas
```bash
python manage.py load_claims data/claims.csv --delimiter '|'
python manage.py load_details data/claims_detail --delimiter '|' 
```
# 6) Run
```bash
python manage.py runserver
```
The application will run at http://127.0.0.1:8000/.
