# Claims Management System – Demo

A small Django + HTMX demo for reviewing medical claims.  
It includes a “user” table view with an HTMX detail panel, notes & flagging, and an **Admin Dashboard** showing average underpayment and claims needing review.

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

## Requirements
- Python **3.10+** (3.12 tested)
- pip / venv
- SQLite (bundled with Python)

## Quickstart

```bash
# 1) Clone
git clone <YOUR_REPO_URL>.git
cd ERISA_Recovery_Dev_Challenge_2025

# 2) Virtualenv
python -m venv .venv
# Windows:
.venv\Scripts\activate
# macOS/Linux:
# source .venv/bin/activate

# 3) Install deps
pip install -r requirements.txt

# 4) Migrate DB
python manage.py migrate

# 5) Run
python manage.py runserver
