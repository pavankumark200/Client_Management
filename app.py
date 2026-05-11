"""
app.py  –  Main Flask application for Insurance Client Management System
Run with:  python app.py
Visit:     http://127.0.0.1:5000
"""

import os
import io
import csv

from pathlib import Path
from datetime import datetime, date

from flask import (
    Flask, render_template, request, redirect, url_for,
    session, flash, jsonify, send_file, abort
)
from werkzeug.security import generate_password_hash, check_password_hash

# ── Load Environment Variables ────────────────────────────────
from dotenv import load_dotenv
load_dotenv()

# ── Scheduler & Email ───────────────────────────────────────────
import time
from threading import Thread
from apscheduler.schedulers.background import BackgroundScheduler
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# ── Local imports ─────────────────────────────────────────────
import sys
sys.path.insert(0, str(Path(__file__).parent))

from config.database import get_db, init_db, UPLOAD_DIR
from config.helpers  import (
    safe_str, safe_float, safe_date, fmt_date, fmt_currency,
    days_until, renewal_status, save_upload, paginate,
    success_json, error_json, row_to_dict, DOC_TYPE_LABELS,
)

# ── App setup ─────────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent
app = Flask(
    __name__,
    template_folder=str(BASE_DIR / "templates"),
    static_folder=str(BASE_DIR / "static"),
)
app.secret_key = os.environ.get("SECRET_KEY", "insurance_cms_secret_2024_xK9!mP")
app.config["MAX_CONTENT_LENGTH"] = 10 * 1024 * 1024   # 10 MB max upload

# ── Template globals ──────────────────────────────────────────
app.jinja_env.globals.update(
    fmt_date=fmt_date,
    fmt_currency=fmt_currency,
    renewal_status=renewal_status,
    days_until=days_until,
    DOC_TYPE_LABELS=DOC_TYPE_LABELS,
    now=datetime.now,
    min=min,   # make Python builtins available in templates
    max=max,
)


# ═════════════════════════════════════════════════════════════
#  AUTH HELPERS
# ═════════════════════════════════════════════════════════════

def login_required(f):
    """Decorator: redirect to login if not authenticated."""
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        if "admin_id" not in session:
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated


# ═════════════════════════════════════════════════════════════
#  AUTH ROUTES
# ═════════════════════════════════════════════════════════════

@app.route("/", methods=["GET"])
def index():
    if "admin_id" in session:
        return redirect(url_for("dashboard"))
    return redirect(url_for("login"))


@app.route("/login", methods=["GET", "POST"])
def login():
    if "admin_id" in session:
        return redirect(url_for("dashboard"))

    error = None
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        db    = get_db()
        admin = db.execute(
            "SELECT * FROM admins WHERE username = ? LIMIT 1", (username,)
        ).fetchone()
        db.close()

        if admin and check_password_hash(admin["password"], password):
            session.clear()
            session["admin_id"]   = admin["id"]
            session["admin_name"] = admin["full_name"]
            session.permanent     = True
            return redirect(url_for("dashboard"))
        else:
            error = "Invalid username or password."

    return render_template("login.html", error=error)


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


# ═════════════════════════════════════════════════════════════
#  DASHBOARD
# ═════════════════════════════════════════════════════════════

@app.route("/dashboard")
@login_required
def dashboard():
    db   = get_db()
    today_str = date.today().isoformat()

    total_clients  = db.execute("SELECT COUNT(*) FROM clients").fetchone()[0]
    active_policies= db.execute(
        "SELECT COUNT(*) FROM clients WHERE status='active'"
    ).fetchone()[0]
    expiring_soon  = db.execute("""
        SELECT COUNT(*) FROM clients
        WHERE status='active'
          AND renewal_date BETWEEN ? AND date(?, '+30 days')
    """, (today_str, today_str)).fetchone()[0]
    expired_count  = db.execute(
        "SELECT COUNT(*) FROM clients WHERE status='expired'"
    ).fetchone()[0]

    recent_clients = db.execute("""
        SELECT id, full_name, phone, policy_type, renewal_date, status
        FROM   clients
        ORDER  BY created_at DESC
        LIMIT  5
    """).fetchall()

    # Clients expiring within 60 days for alert banner
    alerts = db.execute("""
        SELECT id, full_name, phone, policy_number, renewal_date, policy_type
        FROM   clients
        WHERE  status = 'active'
          AND  renewal_date BETWEEN ? AND date(?, '+60 days')
        ORDER  BY renewal_date ASC
        LIMIT  10
    """, (today_str, today_str)).fetchall()

    db.close()
    return render_template(
        "dashboard.html",
        total_clients=total_clients,
        active_policies=active_policies,
        expiring_soon=expiring_soon,
        expired_count=expired_count,
        recent_clients=[row_to_dict(r) for r in recent_clients],
        alerts=[row_to_dict(r) for r in alerts],
        admin_name=session.get("admin_name", "Admin"),
    )


# ═════════════════════════════════════════════════════════════
#  CLIENT LIST  (with pagination)
# ═════════════════════════════════════════════════════════════

@app.route("/clients")
@login_required
def clients():
    page     = max(1, int(request.args.get("page", 1)))
    per_page = 10
    status_f = request.args.get("status", "")
    sort     = request.args.get("sort", "created_at")
    order    = request.args.get("order", "desc")

    # Whitelist sort columns
    allowed_sorts = {"full_name", "renewal_date", "premium_amount",
                     "created_at", "insurance_company", "policy_type"}
    if sort not in allowed_sorts:
        sort = "created_at"
    order = "ASC" if order.lower() == "asc" else "DESC"

    db     = get_db()
    where  = "WHERE status = ?" if status_f else ""
    params = [status_f] if status_f else []

    total = db.execute(
        f"SELECT COUNT(*) FROM clients {where}", params
    ).fetchone()[0]

    pag   = paginate(total, page, per_page)
    rows  = db.execute(
        f"SELECT * FROM clients {where} ORDER BY {sort} {order} LIMIT ? OFFSET ?",
        params + [per_page, pag["offset"]],
    ).fetchall()
    db.close()

    return render_template(
        "clients.html",
        clients=[row_to_dict(r) for r in rows],
        pag=pag,
        status_f=status_f,
        sort=sort,
        order=order.lower(),
        admin_name=session.get("admin_name", "Admin"),
    )


# ═════════════════════════════════════════════════════════════
#  CLIENT CRUD  (API – JSON)
# ═════════════════════════════════════════════════════════════

@app.route("/api/clients", methods=["POST"])
@login_required
def api_add_client():
    f = request.form
    db = get_db()
    try:
        cur = db.execute("""
            INSERT INTO clients
              (full_name, phone, email, address, date_of_birth,
               aadhaar_number, pan_number, policy_type, policy_number,
               insurance_company, premium_amount, policy_start_date, payment_term,
               renewal_date, maturity_date,
               vehicle_number, vehicle_model, nominee_name,
               nominee_relation, nominee_dob, notes, status)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            safe_str(f.get("full_name")),
            safe_str(f.get("phone")),
            safe_str(f.get("email")),
            safe_str(f.get("address")),
            safe_date(f.get("date_of_birth")),
            safe_str(f.get("aadhaar_number")),
            safe_str(f.get("pan_number")),
            safe_str(f.get("policy_type")),
            safe_str(f.get("policy_number")),
            safe_str(f.get("insurance_company")),
            safe_float(f.get("premium_amount")),
            safe_date(f.get("policy_start_date")),
            safe_str(f.get("payment_term")),
            safe_date(f.get("renewal_date")),
            safe_date(f.get("maturity_date")),
            safe_str(f.get("vehicle_number")),
            safe_str(f.get("vehicle_model")),
            safe_str(f.get("nominee_name")),
            safe_str(f.get("nominee_relation")),
            safe_date(f.get("nominee_dob")),
            safe_str(f.get("notes")),
            safe_str(f.get("status")) or "active",
        ))
        db.commit()
        new_id = cur.lastrowid
        db.close()
        return success_json("Client added successfully.", id=new_id)
    except Exception as e:
        db.close()
        return error_json(str(e))


@app.route("/api/clients/<int:client_id>", methods=["GET"])
@login_required
def api_get_client(client_id):
    db  = get_db()
    row = db.execute("SELECT * FROM clients WHERE id=?", (client_id,)).fetchone()
    db.close()
    if not row:
        return error_json("Client not found.", 404)
    return jsonify(row_to_dict(row))


@app.route("/api/clients/<int:client_id>", methods=["PUT"])
@login_required
def api_update_client(client_id):
    f  = request.form
    db = get_db()
    try:
        db.execute("""
            UPDATE clients SET
              full_name=?, phone=?, email=?, address=?, date_of_birth=?,
              aadhaar_number=?, pan_number=?, policy_type=?, policy_number=?,
              insurance_company=?, premium_amount=?, policy_start_date=?, payment_term=?,
              renewal_date=?, maturity_date=?,
              vehicle_number=?, vehicle_model=?, nominee_name=?,
              nominee_relation=?, nominee_dob=?, notes=?, status=?,
              updated_at=datetime('now')
            WHERE id=?
        """, (
            safe_str(f.get("full_name")),
            safe_str(f.get("phone")),
            safe_str(f.get("email")),
            safe_str(f.get("address")),
            safe_date(f.get("date_of_birth")),
            safe_str(f.get("aadhaar_number")),
            safe_str(f.get("pan_number")),
            safe_str(f.get("policy_type")),
            safe_str(f.get("policy_number")),
            safe_str(f.get("insurance_company")),
            safe_float(f.get("premium_amount")),
            safe_date(f.get("policy_start_date")),
            safe_str(f.get("payment_term")),
            safe_date(f.get("renewal_date")),
            safe_date(f.get("maturity_date")),
            safe_str(f.get("vehicle_number")),
            safe_str(f.get("vehicle_model")),
            safe_str(f.get("nominee_name")),
            safe_str(f.get("nominee_relation")),
            safe_date(f.get("nominee_dob")),
            safe_str(f.get("notes")),
            safe_str(f.get("status")) or "active",
            client_id,
        ))
        db.commit()
        db.close()
        return success_json("Client updated successfully.")
    except Exception as e:
        db.close()
        return error_json(str(e))


@app.route("/api/clients/<int:client_id>", methods=["DELETE"])
@login_required
def api_delete_client(client_id):
    db = get_db()
    # Cascade deletes documents too (via FK)
    db.execute("DELETE FROM clients WHERE id=?", (client_id,))
    db.commit()
    db.close()
    # Remove uploaded files
    client_dir = UPLOAD_DIR / "clients" / str(client_id)
    if client_dir.exists():
        import shutil
        shutil.rmtree(client_dir)
    return success_json("Client deleted successfully.")


# ═════════════════════════════════════════════════════════════
#  CLIENT PROFILE  (full detail page)
# ═════════════════════════════════════════════════════════════

@app.route("/clients/<int:client_id>")
@login_required
def client_profile(client_id):
    db     = get_db()
    client = db.execute("SELECT * FROM clients WHERE id=?", (client_id,)).fetchone()
    if not client:
        abort(404)
    docs   = db.execute(
        "SELECT * FROM documents WHERE client_id=? ORDER BY uploaded_at DESC",
        (client_id,)
    ).fetchall()
    db.close()
    return render_template(
        "client_profile.html",
        client=row_to_dict(client),
        docs=[row_to_dict(d) for d in docs],
        admin_name=session.get("admin_name", "Admin"),
    )


# ═════════════════════════════════════════════════════════════
#  SEARCH  (AJAX + full page)
# ═════════════════════════════════════════════════════════════

@app.route("/search")
@login_required
def search():
    return render_template("search.html",
                           admin_name=session.get("admin_name", "Admin"))


@app.route("/api/search")
@login_required
def api_search():
    q     = request.args.get("q", "").strip()
    limit = min(int(request.args.get("limit", 20)), 100)
    if not q:
        return jsonify([])

    like  = f"%{q}%"
    db    = get_db()
    rows  = db.execute("""
        SELECT id, full_name, phone, email, policy_number,
               vehicle_number, policy_type, insurance_company,
               renewal_date, status, premium_amount
        FROM   clients
        WHERE  full_name      LIKE ?
          OR   phone          LIKE ?
          OR   email          LIKE ?
          OR   vehicle_number LIKE ?
          OR   policy_number  LIKE ?
          OR   aadhaar_number LIKE ?
          OR   pan_number     LIKE ?
        ORDER  BY full_name
        LIMIT  ?
    """, (like, like, like, like, like, like, like, limit)).fetchall()
    db.close()
    return jsonify([row_to_dict(r) for r in rows])


# ═════════════════════════════════════════════════════════════
#  RENEWALS / EXPIRY ALERTS
# ═════════════════════════════════════════════════════════════

@app.route("/renewals")
@login_required
def renewals():
    db        = get_db()
    today_str = date.today().isoformat()
    days_30   = "date('" + today_str + "', '+30 days')"
    days_60   = "date('" + today_str + "', '+60 days')"
    days_90   = "date('" + today_str + "', '+90 days')"

    expired = db.execute("""
        SELECT * FROM clients
        WHERE  status='active' AND renewal_date < ?
        ORDER  BY renewal_date
    """, (today_str,)).fetchall()

    due_30 = db.execute(f"""
        SELECT * FROM clients
        WHERE  status='active'
          AND  renewal_date BETWEEN ? AND {days_30}
        ORDER  BY renewal_date
    """, (today_str,)).fetchall()

    due_60 = db.execute(f"""
        SELECT * FROM clients
        WHERE  status='active'
          AND  renewal_date BETWEEN {days_30} AND {days_60}
        ORDER  BY renewal_date
    """).fetchall()

    due_90 = db.execute(f"""
        SELECT * FROM clients
        WHERE  status='active'
          AND  renewal_date BETWEEN {days_60} AND {days_90}
        ORDER  BY renewal_date
    """).fetchall()

    db.close()
    return render_template(
        "renewals.html",
        expired=[row_to_dict(r) for r in expired],
        due_30=[row_to_dict(r) for r in due_30],
        due_60=[row_to_dict(r) for r in due_60],
        due_90=[row_to_dict(r) for r in due_90],
        admin_name=session.get("admin_name", "Admin"),
    )


# ═════════════════════════════════════════════════════════════
#  EMAIL AUTOMATION
# ═════════════════════════════════════════════════════════════

def run_email_alerts():
    """Background task to find clients due in exactly 3 days and send them an Email."""
    def _send():
        from config.database import get_db
        from datetime import date, timedelta

        db = get_db()
        today = date.today()
        target_date = today + timedelta(days=3)
        target_str = target_date.isoformat()

        # SMTP credentials
        sender_email = os.environ.get('SMTP_EMAIL')
        sender_password = os.environ.get('SMTP_PASSWORD')

        if not sender_email or not sender_password:
            print("SMTP credentials missing in environment variables (.env). Aborting email alerts.")
            db.close()
            return

        rows = db.execute(
            "SELECT id, full_name, email, policy_number, renewal_date FROM clients WHERE status='active' AND renewal_date = ?", 
            (target_str,)
        ).fetchall()

        if not rows:
            db.close()
            return

        try:
            # Connect to Gmail SMTP server
            server = smtplib.SMTP('smtp.gmail.com', 587)
            server.starttls()
            server.login(sender_email, sender_password)
        except Exception as e:
            print(f"Failed to connect to email server: {e}")
            db.close()
            return

        for r in rows:
            email_to = r["email"]
            if not email_to:
                continue

            subject = "Insurance Policy Renewal Reminder"
            body = f"Hello {r['full_name']},\n\nThis is an automated reminder that your insurance policy ({r['policy_number'] or 'N/A'}) is due for renewal on {r['renewal_date']}.\n\nPlease ignore this email if you have already paid.\n\nThank you."

            msg = MIMEMultipart()
            msg['From'] = sender_email
            msg['To'] = email_to
            msg['Subject'] = subject
            msg.attach(MIMEText(body, 'plain'))

            try:
                print(f"Sending Email to {email_to}...")
                server.sendmail(sender_email, email_to, msg.as_string())
                print(f"Email sent successfully to {email_to}")

                db.execute(
                    "INSERT INTO notifications_log (client_id, client_name, phone, policy_number, status, error_message) VALUES (?, ?, ?, ?, ?, ?)",
                    (r["id"], r["full_name"], email_to, r["policy_number"], "sent", None)
                )
                db.commit()
            except Exception as e:
                print(f"Failed to send Email to {email_to}: {e}")
                db.execute(
                    "INSERT INTO notifications_log (client_id, client_name, phone, policy_number, status, error_message) VALUES (?, ?, ?, ?, ?, ?)",
                    (r["id"], r["full_name"], email_to, r["policy_number"], "failed", str(e))
                )
                db.commit()

        server.quit()
        db.close()
        print("Finished Email alert batch.")

    t = Thread(target=_send)
    t.start()

@app.route("/api/trigger_email_alerts", methods=["POST"])
@login_required
def trigger_email_alerts():
    """Manually trigger the 3-day Email alert scan."""
    run_email_alerts()
    return success_json("Email alerts triggered. Messages will be sent in the background.")



@app.route("/notifications")
@login_required
def notifications():
    db = get_db()
    rows = db.execute("SELECT * FROM notifications_log ORDER BY sent_at DESC LIMIT 100").fetchall()
    db.close()
    return render_template(
        "notifications.html",
        logs=[dict(r) for r in rows],
        admin_name=session.get("admin_name", "Admin")
    )

# ═════════════════════════════════════════════════════════════
#  DOCUMENT MANAGEMENT
# ═════════════════════════════════════════════════════════════

@app.route("/api/documents/upload", methods=["POST"])
@login_required
def api_upload_document():
    client_id = request.form.get("client_id", type=int)
    doc_type  = request.form.get("doc_type", "other")
    file_obj  = request.files.get("file")

    if not client_id:
        return error_json("client_id is required.")

    result = save_upload(file_obj, client_id, doc_type)
    if not result["success"]:
        return error_json(result["error"])

    db = get_db()
    cur = db.execute("""
        INSERT INTO documents
          (client_id, doc_type, original_name, stored_name, file_path, file_size, mime_type)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (
        client_id,
        doc_type,
        result["original_name"],
        result["stored_name"],
        result["file_path"],
        result["file_size"],
        result["mime_type"],
    ))
    db.commit()
    doc_id = cur.lastrowid
    db.close()
    return success_json("Document uploaded successfully.", doc_id=doc_id)


@app.route("/uploads/<path:filepath>")
@login_required
def serve_upload(filepath):
    """Serve uploaded files securely (auth required)."""
    target = UPLOAD_DIR / filepath
    if not target.exists():
        abort(404)
    # Prevent path traversal
    try:
        target.resolve().relative_to(UPLOAD_DIR.resolve())
    except ValueError:
        abort(403)
    return send_file(str(target))


@app.route("/api/documents/<int:doc_id>/download")
@login_required
def download_document(doc_id):
    db  = get_db()
    doc = db.execute("SELECT * FROM documents WHERE id=?", (doc_id,)).fetchone()
    db.close()
    if not doc:
        abort(404)
    path = UPLOAD_DIR / doc["file_path"]
    if not path.exists():
        abort(404)
    return send_file(
        str(path),
        download_name=doc["original_name"],
        as_attachment=True,
    )


@app.route("/api/documents/<int:doc_id>", methods=["DELETE"])
@login_required
def api_delete_document(doc_id):
    db  = get_db()
    doc = db.execute("SELECT * FROM documents WHERE id=?", (doc_id,)).fetchone()
    if not doc:
        db.close()
        return error_json("Document not found.", 404)
    # Delete physical file
    path = UPLOAD_DIR / doc["file_path"]
    if path.exists():
        path.unlink()
    db.execute("DELETE FROM documents WHERE id=?", (doc_id,))
    db.commit()
    db.close()
    return success_json("Document deleted.")


# ═════════════════════════════════════════════════════════════
#  EXPORT  (Excel CSV + PDF)
# ═════════════════════════════════════════════════════════════

@app.route("/export/csv")
@login_required
def export_csv():
    db   = get_db()
    rows = db.execute("SELECT * FROM clients ORDER BY full_name").fetchall()
    db.close()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "ID","Full Name","Phone","Email","Address","DOB",
        "Aadhaar","PAN","Policy Type","Policy Number",
        "Insurance Company","Premium (₹)","Renewal Date",
        "Vehicle Number","Vehicle Model","Nominee","Relation","Status","Created At"
    ])
    for r in rows:
        r = dict(r)
        writer.writerow([
            r["id"], r["full_name"], r["phone"], r["email"], r["address"],
            r["date_of_birth"], r["aadhaar_number"], r["pan_number"],
            r["policy_type"], r["policy_number"], r["insurance_company"],
            r["premium_amount"], r["renewal_date"], r["vehicle_number"],
            r["vehicle_model"], r["nominee_name"], r["nominee_relation"],
            r["status"], r["created_at"],
        ])

    output.seek(0)
    return send_file(
        io.BytesIO(output.getvalue().encode("utf-8-sig")),
        mimetype="text/csv",
        as_attachment=True,
        download_name=f"clients_export_{date.today()}.csv",
    )


@app.route("/export/pdf")
@login_required
def export_pdf():
    """Generate a simple PDF report using ReportLab."""
    try:
        from reportlab.lib.pagesizes import A4, landscape
        from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
        from reportlab.lib.styles import getSampleStyleSheet
        from reportlab.lib import colors
    except ImportError:
        return "ReportLab not installed. Run: pip install reportlab", 500

    db   = get_db()
    rows = db.execute(
        "SELECT full_name,phone,email,policy_type,policy_number,insurance_company,premium_amount,renewal_date,status FROM clients ORDER BY full_name"
    ).fetchall()
    db.close()

    buf    = io.BytesIO()
    doc    = SimpleDocTemplate(buf, pagesize=landscape(A4), leftMargin=20, rightMargin=20)
    styles = getSampleStyleSheet()
    elems  = []

    elems.append(Paragraph("Insurance CMS – Client Report", styles["Title"]))
    elems.append(Paragraph(f"Generated: {datetime.now().strftime('%d %b %Y %H:%M')}", styles["Normal"]))
    elems.append(Spacer(1, 12))

    headers = ["Name","Phone","Email","Policy Type","Policy No.","Company","Premium","Renewal","Status"]
    data    = [headers]
    for r in rows:
        r = dict(r)
        data.append([
            r["full_name"], r["phone"] or "", r["email"] or "",
            r["policy_type"] or "", r["policy_number"] or "",
            r["insurance_company"] or "",
            f"₹{r['premium_amount']:,.0f}" if r["premium_amount"] else "",
            fmt_date(r["renewal_date"]) if r["renewal_date"] else "",
            (r["status"] or "").capitalize(),
        ])

    tbl = Table(data, repeatRows=1)
    tbl.setStyle(TableStyle([
        ("BACKGROUND",  (0,0), (-1,0), colors.HexColor("#1a237e")),
        ("TEXTCOLOR",   (0,0), (-1,0), colors.white),
        ("FONTNAME",    (0,0), (-1,0), "Helvetica-Bold"),
        ("FONTSIZE",    (0,0), (-1,-1), 8),
        ("ROWBACKGROUNDS",(0,1),(-1,-1),[colors.white, colors.HexColor("#f0f4ff")]),
        ("GRID",        (0,0), (-1,-1), 0.3, colors.grey),
        ("VALIGN",      (0,0), (-1,-1), "MIDDLE"),
        ("LEFTPADDING", (0,0), (-1,-1), 4),
        ("RIGHTPADDING",(0,0), (-1,-1), 4),
    ]))
    elems.append(tbl)
    doc.build(elems)

    buf.seek(0)
    return send_file(
        buf,
        mimetype="application/pdf",
        as_attachment=True,
        download_name=f"clients_report_{date.today()}.pdf",
    )


# ═════════════════════════════════════════════════════════════
#  SETTINGS  (change password)
# ═════════════════════════════════════════════════════════════

@app.route("/settings", methods=["GET", "POST"])
@login_required
def settings():
    msg = None
    error = None
    if request.method == "POST":
        current  = request.form.get("current_password", "")
        new_pw   = request.form.get("new_password", "")
        confirm  = request.form.get("confirm_password", "")

        db    = get_db()
        admin = db.execute("SELECT * FROM admins WHERE id=?",
                           (session["admin_id"],)).fetchone()
        if not check_password_hash(admin["password"], current):
            error = "Current password is incorrect."
        elif len(new_pw) < 6:
            error = "New password must be at least 6 characters."
        elif new_pw != confirm:
            error = "Passwords do not match."
        else:
            db.execute("UPDATE admins SET password=? WHERE id=?",
                       (generate_password_hash(new_pw), session["admin_id"]))
            db.commit()
            msg = "Password changed successfully."
        db.close()

    return render_template("settings.html",
                           admin_name=session.get("admin_name", "Admin"),
                           msg=msg, error=error)


# ═════════════════════════════════════════════════════════════
#  ERROR HANDLERS
# ═════════════════════════════════════════════════════════════

@app.errorhandler(404)
def not_found(e):
    return render_template("404.html",
                           admin_name=session.get("admin_name", "Admin")), 404


@app.errorhandler(413)
def too_large(e):
    return jsonify({"success": False, "error": "File too large (max 10 MB)."}), 413


# ═════════════════════════════════════════════════════════════
#  ENTRY POINT
# ═════════════════════════════════════════════════════════════

if __name__ == "__main__":
    init_db()   # create tables + seed demo data on first run
    
    # Start the background scheduler
    scheduler = BackgroundScheduler()
    scheduler.add_job(func=run_email_alerts, trigger="cron", hour=10, minute=0)
    scheduler.start()

    print("=" * 55)
    print("  Insurance CMS  –  http://127.0.0.1:5000")
    print("  Login:  admin  /  Admin@1234")
    print("=" * 55)
    app.run(debug=True, port=5000)
