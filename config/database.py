"""
database.py  –  SQLite helper for Insurance CMS
Provides get_db() context and init_db() bootstrap.
"""

import sqlite3
import os
from pathlib import Path
from werkzeug.security import generate_password_hash

# Resolve paths relative to this file
BASE_DIR   = Path(__file__).resolve().parent.parent
DB_PATH    = BASE_DIR / "database" / "insurance.db"
UPLOAD_DIR = BASE_DIR / "uploads"


def get_db() -> sqlite3.Connection:
    """Return a new SQLite connection with row_factory set."""
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row          # rows behave like dicts
    conn.execute("PRAGMA journal_mode=WAL") # better concurrency
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db() -> None:
    """
    Create all tables and seed demo data if DB is empty.
    Called once when app.py starts.
    """
    os.makedirs(DB_PATH.parent, exist_ok=True)
    os.makedirs(UPLOAD_DIR,     exist_ok=True)

    conn = get_db()
    cur  = conn.cursor()

    # ── Admins ──────────────────────────────────────────────────
    cur.execute("""
        CREATE TABLE IF NOT EXISTS admins (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            username   TEXT    NOT NULL UNIQUE,
            password   TEXT    NOT NULL,
            full_name  TEXT    NOT NULL,
            email      TEXT,
            created_at TEXT    DEFAULT (datetime('now'))
        )
    """)

    # ── Clients ─────────────────────────────────────────────────
    cur.execute("""
        CREATE TABLE IF NOT EXISTS clients (
            id                 INTEGER PRIMARY KEY AUTOINCREMENT,
            full_name          TEXT    NOT NULL,
            phone              TEXT,
            email              TEXT,
            address            TEXT,
            date_of_birth      TEXT,
            aadhaar_number     TEXT,
            pan_number         TEXT,
            policy_type        TEXT,
            policy_number      TEXT,
            insurance_company  TEXT,
            premium_amount     REAL,
            renewal_date       TEXT,
            vehicle_number     TEXT,
            vehicle_model      TEXT,
            nominee_name       TEXT,
            nominee_relation   TEXT,
            nominee_dob        TEXT,
            notes              TEXT,
            status             TEXT    DEFAULT 'active',
            created_at         TEXT    DEFAULT (datetime('now')),
            updated_at         TEXT    DEFAULT (datetime('now'))
        )
    """)

    # ── Documents ───────────────────────────────────────────────
    cur.execute("""
        CREATE TABLE IF NOT EXISTS documents (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            client_id     INTEGER NOT NULL,
            doc_type      TEXT    DEFAULT 'other',
            original_name TEXT    NOT NULL,
            stored_name   TEXT    NOT NULL,
            file_path     TEXT    NOT NULL,
            file_size     INTEGER,
            mime_type     TEXT,
            uploaded_at   TEXT    DEFAULT (datetime('now')),
            FOREIGN KEY (client_id) REFERENCES clients(id) ON DELETE CASCADE
        )
    """)

    # ── Default admin (password: Admin@1234) ─────────────────────
    cur.execute("SELECT COUNT(*) FROM admins")
    if cur.fetchone()[0] == 0:
        cur.execute("""
            INSERT INTO admins (username, password, full_name, email)
            VALUES (?, ?, ?, ?)
        """, (
            "admin",
            generate_password_hash("Admin@1234"),
            "System Administrator",
            "admin@insurancecms.com",
        ))

    # ── Demo data ────────────────────────────────────────────────
    cur.execute("SELECT COUNT(*) FROM clients")
    if cur.fetchone()[0] == 0:
        demo = [
            ("Rajesh Kumar",   "9876543210", "rajesh@example.com",
             "12, MG Road, Bengaluru - 560001",    "1985-06-15",
             "1234 5678 9012", "ABCPK1234D",
             "Motor Insurance",  "POL-2024-001", "LIC of India",       12500.00, "2025-06-15",
             "KA01AB1234", "Honda City",   "Priya Kumar",   "Spouse", None, None, "active"),

            ("Anita Sharma",   "9123456789", "anita.sharma@example.com",
             "45, Anna Nagar, Chennai - 600040",   "1990-03-22",
             "9876 5432 1098", "BCDSH5678E",
             "Life Insurance",   "POL-2024-002", "HDFC Life",          25000.00, "2025-03-22",
             None, None,          "Suresh Sharma", "Husband", None, "VIP client", "active"),

            ("Mohammed Irfan", "8765432109", "irfan@example.com",
             "78, Park Street, Kolkata - 700016",  "1978-11-10",
             "5432 1098 7654", "CDEIR8901F",
             "Health Insurance", "POL-2024-003", "Star Health",         8000.00, "2024-11-10",
             None, None,          "Fatima Irfan",  "Spouse", None, None, "expired"),

            ("Sunita Patel",   "7654321098", "sunita.patel@example.com",
             "23, Navrangpura, Ahmedabad - 380009","1995-07-30",
             "8765 4321 0987", "DEFPA2345G",
             "Motor Insurance",  "POL-2024-004", "Bajaj Allianz",       9500.00, "2025-07-30",
             "GJ01CD5678", "Maruti Swift", "Ramesh Patel",  "Father", None, None, "active"),

            ("Vikram Singh",   "6543210987", "vikram.singh@example.com",
             "56, Connaught Place, New Delhi-110001","1982-09-05",
             "4321 0987 6543", "EFGSI3456H",
             "Life Insurance",   "POL-2024-005", "SBI Life",           35000.00, "2025-09-05",
             None, None,          "Meena Singh",   "Spouse", None, "Premium plan", "active"),

            ("Lakshmi Reddy",  "5432109876", "lakshmi.reddy@example.com",
             "89, Banjara Hills, Hyderabad-500034","1988-12-20",
             "3210 9876 5432", "FGHRE4567I",
             "Motor Insurance",  "POL-2024-006", "New India Assurance", 11000.00, "2024-12-20",
             "TS09EF7890", "Hyundai i20",  "Ravi Reddy",    "Husband", None, None, "expired"),

            ("Arjun Nair",     "4321098765", "arjun.nair@example.com",
             "34, MG Road, Kochi - 682011",        "1992-04-14",
             "2109 8765 4321", "GHINA5678J",
             "Health Insurance", "POL-2024-007", "Apollo Munich",      15000.00, "2025-04-14",
             None, None,          "Deepa Nair",    "Mother", None, None, "active"),

            ("Pooja Mehta",    "3210987654", "pooja.mehta@example.com",
             "67, FC Road, Pune - 411004",          "1998-01-25",
             "1098 7654 3210", "HIJME6789K",
             "Motor Insurance",  "POL-2024-008", "ICICI Lombard",       7500.00, "2025-01-25",
             "MH12GH9012", "Tata Nexon",   "Sunil Mehta",   "Father", None, "Young driver", "active"),
        ]
        cur.executemany("""
            INSERT INTO clients
              (full_name,phone,email,address,date_of_birth,
               aadhaar_number,pan_number,policy_type,policy_number,
               insurance_company,premium_amount,renewal_date,
               vehicle_number,vehicle_model,nominee_name,nominee_relation,
               nominee_dob,notes,status)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, demo)

    conn.commit()
    conn.close()
