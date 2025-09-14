Claims Management System – Demo

A small Django + HTMX demo for reviewing medical claims.
It includes a “user” table view with an HTMX detail panel, notes & flagging, and an Admin Dashboard showing average underpayment and claims needing review.

Features

Welcome page → choose User or Admin flows

User page (/user/)

Paginated claims table with status pills (Paid / Under Review / Denied)

Click View to load a claim detail panel (HTMX partial)

Add Note (inline form, instant append)

Flag for Review (confirm dialog; prevents re-flagging if already Under Review)

Admin dashboard (/dashboard/)

Average underpayment across all claims

“Claims Needing Review” table (same visual style as user table)

Flag button disabled on admin side

HTMX-driven partials for smooth UI without a SPA framework

Requirements

Python 3.10+ (3.12 tested)

pip / venv

SQLite (bundled with Python)

No Node / npm is required.

Quickstart
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

# (Optional) If the repo includes a pre-populated db.sqlite3, you can skip creating data.
# Otherwise, load your own fixture or create a few Claim records via the Django shell/admin.

# 5) Run
python manage.py runserver


Now open:

Welcome: http://127.0.0.1:8000/welcome/

(Root / redirects to the welcome page.)

User: http://127.0.0.1:8000/user/

Admin dashboard: http://127.0.0.1:8000/dashboard/

This project does not expose Django’s built-in /admin/ unless you add it yourself.
The app’s admin view is /dashboard/.

How to use
User page (/user/)

Browse the claims table.

Click View to load details on the same page (right panel).

In the detail panel:

Add Note → opens an inline form; submit to append the note instantly.

Flag for Review → shows a confirmation dialog; on confirm, the claim status becomes Under Review.

If a claim is already under review, you’ll see an Already requested dialog and the flag button becomes disabled.

Admin dashboard (/dashboard/)

Shows a metric: Average Underpayment

“Claims Needing Review” table lists flagged items.

Click View to load the same HTMX detail panel below the table.

The Flag button is disabled to prevent duplicate actions from the admin side.

Project structure (high-level)
claims_demo/                 # Django project settings
│
├─ claims/                   # App
│  ├─ templates/claims/
│  │  ├─ base.html
│  │  ├─ welcome.html
│  │  ├─ index.html                  # user page shell
│  │  ├─ admin_dashboard.html        # admin page shell
│  │  ├─ _claim_table.html           # table partial (user/admin share the style)
│  │  ├─ _detail_panel.html          # claim details partial (HTMX target)
│  │  ├─ _notes_card.html            # notes list + add form
│  │  ├─ _flag_button.html           # flag button (HTMX)
│  │  ├─ _confirm_review.html        # confirm modal partial
│  │  └─ _already_review.html        # “already under review” notice
│  ├─ urls.py
│  └─ views.py
│
├─ manage.py
└─ db.sqlite3                # (may be present with demo data)

Key URLs
Path	Name	Purpose
/welcome/	claims:welcome	Landing page with “User / Admin” choices
/user/	claims:index	User table view with HTMX detail panel
/dashboard/	claims:admin_dashboard	Admin dashboard (average underpayment + review queue)
/claim/<pk>/	claims:claim_detail	HTMX partial: loads the claim detail panel
/detail/<pk>/	claims:detail	(Alias for detail partial in some templates)
/flag/confirm/<pk>/	claims:flag_confirm	HTMX partial: “Confirm flag” dialog
/flag/set/<pk>/	claims:flag_set	Sets claim to “Under Review” (HTMX swap)
/note/add/<pk>/	claims:add_note	Adds a note and refreshes the notes list

Templates use the claims: namespace in {% url %}.

How it works (HTMX)

Loading details:
Buttons with hx-get="{% url 'claims:claim_detail' pk %}" hx-target="#detail-panel" hx-swap="innerHTML" fetch a partial and inject it into the panel.

Flagging:

Click → open _confirm_review.html (HX GET)

Confirm → POST /flag/set/<pk>/
The server updates status and returns a small HTML fragment to swap just the affected parts (flag button, status pill).

If the claim is already under review, server returns _already_review.html.

Notes:

The add form POSTs via HTMX, server responds with the updated notes list and resets the form (via hx-on:htmx:afterSwap in the markup).

Troubleshooting

“Reverse for 'detail' not found”
Make sure templates use the namespaced URL (e.g. {% url 'claims:detail' c.pk %}) and claims_demo/urls.py includes the app with a namespace:

path("", include(("claims.urls", "claims"), namespace="claims")),


Status pill doesn’t render for some rows
Update to the bundled _claim_table.html. It normalizes both enum values (e.g. under_review) and display strings (e.g. Under Review) so they render consistently.

Trying /admin/ gives 404
This app’s admin view is at /dashboard/.
(If you want Django’s built-in admin, add path('admin/', admin.site.urls) to claims_demo/urls.py and run createsuperuser.)

Development
# optional: create a superuser if you enable Django admin
python manage.py createsuperuser

# run with reload
python manage.py runserver


Debug is enabled by default in local settings.

Static files are simple inline CSS/SVG; no build step.

License

Add your preferred license here (e.g., MIT).
