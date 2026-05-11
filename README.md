# Client_Management
client management tool

# Insurance CMS — Setup Instructions

## Prerequisites
- Python 3.10+  (https://python.org)
- pip

---

## Step 1 — Install dependencies

Open a terminal inside the `insurance_cms/` folder and run:

```
pip install -r requirements.txt
```

---

## Step 2 — Run the application

```
python app.py
```

The console will print:
```
  Insurance CMS  –  http://127.0.0.1:5000
  Login:  admin  /  Admin@1234
```

Open **http://127.0.0.1:5000** in your browser.

---

## Step 3 — First login

| Field    | Value       |
|----------|-------------|
| Username | `admin`     |
| Password | `Admin@1234`|

Change the password immediately via **Settings → Change Password**.

---

## Folder Structure

```
insurance_cms/
├── app.py                  ← Flask application (entry point)
├── requirements.txt
├── config/
│   ├── database.py         ← SQLite connection + init_db()
│   ├── helpers.py          ← Utility functions
│   └── auth.py             ← (PHP files — DELETE THESE)
├── database/
│   └── insurance.db        ← Auto-created on first run
├── uploads/
│   └── clients/<id>/       ← Uploaded documents (auto-created)
├── static/
│   ├── css/style.css
│   └── js/main.js
└── templates/
    ├── layout.html
    ├── login.html
    ├── dashboard.html
    ├── clients.html
    ├── client_profile.html
    ├── search.html
    ├── renewals.html
    ├── settings.html
    ├── 404.html
    └── partials/
        └── client_modal.html
```

---

## Cleanup — Delete PHP files (not needed)

Remove these files that were created before switching to Python:

```
insurance_cms/config/database.php
insurance_cms/config/auth.php
insurance_cms/config/helpers.php
insurance_cms/database/schema.sql
```

---

## Features Summary

| Feature | Details |
|---------|---------|
| Auth | Admin login, bcrypt password, session |
| Dashboard | Stats cards, recent clients, 60-day alert banner |
| Clients | Full CRUD, sortable table, pagination, status filter |
| Search | AJAX universal search (name/phone/email/vehicle/policy) |
| Profile | All client details, policy, vehicle, nominee, documents |
| Documents | Upload PDF/JPG/PNG, preview, download, delete |
| Renewals | Grouped by expired / 30d / 60d / 90d |
| Export | CSV & PDF (ReportLab) |
| Settings | Change password |
| Dark mode | Toggle in topbar, persisted in localStorage |
| Mobile | Responsive sidebar + layout |

---

## Credentials after password change

Store your new credentials safely — the DB is in `database/insurance.db`.
