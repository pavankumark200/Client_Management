"""
helpers.py  –  Utility functions for Insurance CMS
"""

import os
import uuid
from datetime import datetime, date
from pathlib import Path
from flask import jsonify

BASE_DIR   = Path(__file__).resolve().parent.parent
UPLOAD_DIR = BASE_DIR / "uploads"

ALLOWED_EXTENSIONS = {"jpg", "jpeg", "png", "pdf"}
MAX_FILE_BYTES     = 10 * 1024 * 1024   # 10 MB

DOC_TYPE_LABELS = {
    "aadhaar":       "Aadhaar Card",
    "pan":           "PAN Card",
    "rc_book":       "RC Book",
    "policy_pdf":    "Policy PDF",
    "passport_photo":"Passport Photo",
    "other":         "Other",
}


# ── Sanitisation ──────────────────────────────────────────────

def safe_str(val) -> str:
    return str(val).strip() if val is not None else ""


def safe_float(val):
    try:
        return float(val)
    except (TypeError, ValueError):
        return None


def safe_date(val: str):
    """Validate a YYYY-MM-DD date string; return it or None."""
    if not val:
        return None
    try:
        datetime.strptime(val, "%Y-%m-%d")
        return val
    except ValueError:
        return None


# ── Date formatting ───────────────────────────────────────────

def fmt_date(val: str, fmt: str = "%d %b %Y") -> str:
    if not val:
        return "–"
    try:
        return datetime.strptime(val[:10], "%Y-%m-%d").strftime(fmt)
    except ValueError:
        return val


def days_until(date_str: str):
    """Return days until a date (negative = past)."""
    if not date_str:
        return None
    try:
        target = datetime.strptime(date_str[:10], "%Y-%m-%d").date()
        return (target - date.today()).days
    except ValueError:
        return None


def renewal_status(renewal_date: str) -> dict:
    """Return a dict with label and css class for renewal badge."""
    days = days_until(renewal_date)
    if days is None:
        return {"label": "Unknown", "cls": "badge-secondary"}
    if days < 0:
        return {"label": "Expired",        "cls": "badge-expired"}
    if days <= 30:
        return {"label": f"Due in {days}d", "cls": "badge-danger"}
    if days <= 60:
        return {"label": f"Due in {days}d", "cls": "badge-warning"}
    return {"label": "Active",             "cls": "badge-success"}


# ── Currency ──────────────────────────────────────────────────

def fmt_currency(val) -> str:
    try:
        return f"₹{float(val):,.2f}"
    except (TypeError, ValueError):
        return "–"


# ── File Upload ───────────────────────────────────────────────

def allowed_file(filename: str) -> bool:
    return "." in filename and \
           filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def save_upload(file_obj, client_id: int, doc_type: str) -> dict:
    """
    Save an uploaded file and return a dict with stored metadata.
    `file_obj` is a Werkzeug FileStorage object.
    """
    if not file_obj or file_obj.filename == "":
        return {"success": False, "error": "No file selected."}

    if not allowed_file(file_obj.filename):
        return {"success": False, "error": "Invalid file type. Allowed: JPG, PNG, PDF."}

    # Read into memory to check size
    data = file_obj.read()
    if len(data) > MAX_FILE_BYTES:
        return {"success": False, "error": "File too large (max 10 MB)."}

    ext         = file_obj.filename.rsplit(".", 1)[1].lower()
    stored_name = f"{uuid.uuid4().hex}.{ext}"
    client_dir  = UPLOAD_DIR / "clients" / str(client_id)
    client_dir.mkdir(parents=True, exist_ok=True)

    dest = client_dir / stored_name
    dest.write_bytes(data)

    rel_path = f"clients/{client_id}/{stored_name}"
    return {
        "success":       True,
        "original_name": file_obj.filename,
        "stored_name":   stored_name,
        "file_path":     rel_path,
        "file_size":     len(data),
        "mime_type":     file_obj.mimetype or "application/octet-stream",
    }


# ── Pagination ────────────────────────────────────────────────

def paginate(total: int, page: int, per_page: int) -> dict:
    total_pages = max(1, -(-total // per_page))   # ceiling division
    page        = max(1, min(page, total_pages))
    offset      = (page - 1) * per_page
    return {
        "total":       total,
        "page":        page,
        "per_page":    per_page,
        "total_pages": total_pages,
        "offset":      offset,
    }


# ── JSON helpers ──────────────────────────────────────────────

def success_json(message: str, **extra):
    return jsonify({"success": True, "message": message, **extra})


def error_json(message: str, status: int = 400):
    return jsonify({"success": False, "error": message}), status


# ── Row → dict ────────────────────────────────────────────────

def row_to_dict(row) -> dict:
    """Convert a sqlite3.Row to a plain dict."""
    return dict(row) if row else {}
