from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from pathlib import Path
import sqlite3, re, csv, io, os, smtplib, ssl, json
from email.message import EmailMessage
from datetime import datetime
from email_validator import validate_email, EmailNotValidError

BASE = Path(__file__).resolve().parent
DB = BASE / "data" / "email_suite.db"
app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "change-this-local-demo-key")

CONFIG_FILE = BASE / "brevo_settings.json"

def load_brevo_settings():
    if CONFIG_FILE.exists():
        try: return json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
        except Exception: return {}
    return {}

def save_brevo_settings(values):
    CONFIG_FILE.write_text(json.dumps(values, indent=2), encoding="utf-8")
    try: os.chmod(CONFIG_FILE, 0o600)
    except OSError: pass


def db():
    DB.parent.mkdir(exist_ok=True)
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    return con

def init_db():
    with db() as con:
        con.executescript("""
        CREATE TABLE IF NOT EXISTS contacts(
          id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL,
          email TEXT NOT NULL UNIQUE, city TEXT DEFAULT '', segment TEXT DEFAULT 'General',
          consent INTEGER DEFAULT 1, created_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS campaigns(
          id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL,
          subject TEXT NOT NULL, template TEXT NOT NULL, status TEXT DEFAULT 'Draft',
          created_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS tests(
          id INTEGER PRIMARY KEY AUTOINCREMENT, campaign_id INTEGER NOT NULL,
          variant_a TEXT NOT NULL, variant_b TEXT NOT NULL, winner TEXT DEFAULT '',
          created_at TEXT NOT NULL);
        """)
        count = con.execute("SELECT COUNT(*) FROM contacts").fetchone()[0]
        if count == 0:
            sample = [
              ("Aarav Sharma","aarav@example.com","Mumbai","OTT Viewers",1),
              ("Diya Patel","diya@example.com","Pune","New Subscribers",1),
              ("Kabir Mehta","kabir@example.com","Mumbai","OTT Viewers",1),
              ("Mira Nair","mira@example.com","Thane","Inactive Users",0),
            ]
            con.executemany("INSERT INTO contacts(name,email,city,segment,consent,created_at) VALUES(?,?,?,?,?,?)",
              [(*x, datetime.now().isoformat(timespec="minutes")) for x in sample])

@app.route("/")
def dashboard():
    with db() as con:
        contacts = con.execute("SELECT COUNT(*) FROM contacts").fetchone()[0]
        campaigns = con.execute("SELECT COUNT(*) FROM campaigns").fetchone()[0]
        tests = con.execute("SELECT COUNT(*) FROM tests").fetchone()[0]
        recent = con.execute("SELECT * FROM campaigns ORDER BY id DESC LIMIT 5").fetchall()
    return render_template("dashboard.html", contacts=contacts, campaigns=campaigns, tests=tests, recent=recent)

@app.route("/contacts", methods=["GET","POST"])
def contacts():
    if request.method == "POST":
        name, email = request.form.get("name","").strip(), request.form.get("email","").strip()
        try:
            validate_email(email, check_deliverability=False)
            if not name: raise ValueError("Name is required.")
            with db() as con:
                con.execute("INSERT INTO contacts(name,email,city,segment,consent,created_at) VALUES(?,?,?,?,?,?)",
                  (name,email,request.form.get("city","").strip(),request.form.get("segment","General"),
                   1 if request.form.get("consent") else 0,datetime.now().isoformat(timespec="minutes")))
            flash("Contact added.")
        except (EmailNotValidError, ValueError) as e: flash(str(e))
        except sqlite3.IntegrityError: flash("That email address already exists.")
        return redirect(url_for("contacts"))
    segment = request.args.get("segment","")
    with db() as con:
        rows = con.execute("SELECT * FROM contacts WHERE (?='' OR segment=?) ORDER BY id DESC",(segment,segment)).fetchall()
        segments = [r[0] for r in con.execute("SELECT DISTINCT segment FROM contacts ORDER BY segment")]
    return render_template("contacts.html", rows=rows, segments=segments, selected=segment)

@app.route("/contacts/import", methods=["POST"])
def import_contacts():
    upload = request.files.get("csv_file")
    if not upload or not upload.filename.lower().endswith(".csv"):
        flash("Choose a CSV file."); return redirect(url_for("contacts"))
    stream = io.StringIO(upload.stream.read().decode("utf-8-sig"))
    reader = csv.DictReader(stream)
    added, skipped = 0, 0
    with db() as con:
        for row in reader:
            try:
                name, email = row.get("name","").strip(), row.get("email","").strip()
                validate_email(email, check_deliverability=False)
                if not name: raise ValueError()
                con.execute("INSERT INTO contacts(name,email,city,segment,consent,created_at) VALUES(?,?,?,?,?,?)",
                  (name,email,row.get("city","").strip(),row.get("segment","General").strip() or "General",
                   1 if row.get("consent","1").strip().lower() in ("1","true","yes","y") else 0,
                   datetime.now().isoformat(timespec="minutes")))
                added += 1
            except Exception: skipped += 1
    flash(f"Import complete: {added} added, {skipped} skipped.")
    return redirect(url_for("contacts"))

@app.route("/campaigns", methods=["GET","POST"])
def campaigns():
    if request.method == "POST":
        name=request.form.get("name","").strip()
        subject=request.form.get("subject","").strip()
        template=request.form.get("template","welcome")
        if name and subject:
            with db() as con:
                con.execute("INSERT INTO campaigns(name,subject,template,status,created_at) VALUES(?,?,?,'Draft',?)",
                  (name,subject,template,datetime.now().isoformat(timespec="minutes")))
            flash("Campaign saved as Draft.")
        else: flash("Campaign name and subject are required.")
        return redirect(url_for("campaigns"))
    with db() as con: rows=con.execute("SELECT * FROM campaigns ORDER BY id DESC").fetchall()
    return render_template("campaigns.html", rows=rows)

@app.route("/campaigns/<int:campaign_id>/preview")
def preview(campaign_id):
    with db() as con: c=con.execute("SELECT * FROM campaigns WHERE id=?",(campaign_id,)).fetchone()
    if not c: return "Campaign not found",404
    sample={"name":"Nancy","email":"nancy@example.com"}
    return render_template("email_preview.html", campaign=c, sample=sample)

@app.route("/campaigns/<int:campaign_id>/qa")
def qa(campaign_id):
    with db() as con: c=con.execute("SELECT * FROM campaigns WHERE id=?",(campaign_id,)).fetchone()
    if not c: return "Campaign not found",404
    checks=[
      ("Subject line present",bool(c["subject"].strip()),"Campaign subject must not be blank."),
      ("Personalization fallback supported",True,"Use a fallback when first name is missing."),
      ("Mobile-friendly layout",True,"Templates use a fluid 600px table layout."),
      ("Unsubscribe placeholder present",True,"Add a real preference/unsubscribe URL before sending."),
      ("Sender domain authenticated",False,"Verify SPF, DKIM and DMARC on your sending domain."),
      ("Cross-client rendering tested",False,"Test in Gmail, Outlook and Apple Mail / Litmus."),
      ("Links verified",False,"Click every CTA and footer link before deployment."),
    ]
    return render_template("qa.html", campaign=c, checks=checks)

@app.route("/ab-testing", methods=["GET","POST"])
def ab_testing():
    if request.method=="POST":
        cid=request.form.get("campaign_id")
        a=request.form.get("variant_a","").strip(); b=request.form.get("variant_b","").strip()
        if cid and a and b:
            with db() as con:
                con.execute("INSERT INTO tests(campaign_id,variant_a,variant_b,created_at) VALUES(?,?,?,?)",
                  (cid,a,b,datetime.now().isoformat(timespec="minutes")))
            flash("A/B test plan saved. No emails were sent.")
        return redirect(url_for("ab_testing"))
    with db() as con:
        campaigns=con.execute("SELECT id,name FROM campaigns ORDER BY id DESC").fetchall()
        tests=con.execute("SELECT tests.*,campaigns.name FROM tests JOIN campaigns ON campaigns.id=tests.campaign_id ORDER BY tests.id DESC").fetchall()
    return render_template("ab_testing.html", campaigns=campaigns, tests=tests)

@app.route("/reports")
def reports():
    with db() as con:
        total=con.execute("SELECT COUNT(*) FROM contacts").fetchone()[0]
        opted=con.execute("SELECT COUNT(*) FROM contacts WHERE consent=1").fetchone()[0]
        by_segment=con.execute("SELECT segment,COUNT(*) AS total FROM contacts GROUP BY segment ORDER BY total DESC").fetchall()
        campaign_rows=con.execute("SELECT status,COUNT(*) AS total FROM campaigns GROUP BY status").fetchall()
    return render_template("reports.html", total=total, opted=opted, by_segment=by_segment, campaign_rows=campaign_rows)

@app.route("/builder")
def builder():
    return render_template("builder.html")

@app.route("/templates")
def templates():
    return render_template("templates.html")

@app.route("/email/<template_name>")
def email_template(template_name):
    if template_name not in ("welcome","promotion","newsletter"): return "Template not found",404
    return render_template(f"emails/{template_name}.html", name=request.args.get("name","Nancy"), offer=request.args.get("offer","25% OFF"))


@app.route("/brevo", methods=["GET", "POST"])
def brevo_settings():
    settings = load_brevo_settings()
    if request.method == "POST":
        login=request.form.get("smtp_login", "").strip(); key=request.form.get("smtp_key", "").strip()
        sender=request.form.get("sender_email", "").strip(); sender_name=request.form.get("sender_name", "MailStudio Pro").strip() or "MailStudio Pro"
        try:
            validate_email(login, check_deliverability=False); validate_email(sender, check_deliverability=False)
            if not key: raise ValueError("SMTP key is required.")
            save_brevo_settings({"smtp_login":login,"smtp_key":key,"sender_email":sender,"sender_name":sender_name})
            flash("Brevo SMTP settings saved on this computer.")
        except (EmailNotValidError, ValueError) as exc: flash(str(exc))
        return redirect(url_for("brevo_settings"))
    return render_template("brevo.html", configured=bool(settings.get("smtp_key")), smtp_login=settings.get("smtp_login", ""), sender_email=settings.get("sender_email", ""), sender_name=settings.get("sender_name", "MailStudio Pro"))

@app.route("/send-test", methods=["POST"])
def send_test_email():
    settings=load_brevo_settings(); recipient=request.form.get("recipient", "").strip()
    subject=request.form.get("subject", "MailStudio Pro — Test email").strip(); body=request.form.get("body", "Test email from MailStudio Pro using Brevo SMTP.").strip()
    try:
        validate_email(recipient, check_deliverability=False)
        if not settings.get("smtp_login") or not settings.get("smtp_key") or not settings.get("sender_email"): raise ValueError("Save Brevo SMTP settings first.")
        msg=EmailMessage(); msg["Subject"]=subject or "MailStudio Pro — Test email"
        msg["From"]=f'{settings.get("sender_name", "MailStudio Pro")} <{settings["sender_email"]}>'; msg["To"]=recipient; msg.set_content(body)
        with smtplib.SMTP("smtp-relay.brevo.com", 587, timeout=25) as server:
            server.ehlo(); server.starttls(context=ssl.create_default_context()); server.ehlo()
            server.login(settings["smtp_login"], settings["smtp_key"]); server.send_message(msg)
        flash(f"Brevo accepted the test email for {recipient}. Check inbox and spam.")
    except (EmailNotValidError, ValueError, smtplib.SMTPException, OSError) as exc: flash(f"Test email failed: {exc}")
    return redirect(url_for("brevo_settings"))


@app.route("/send-html", methods=["GET", "POST"])
def send_html_email():
    if request.method == "POST":
        settings = load_brevo_settings()
        recipient = request.form.get("recipient", "").strip()
        subject = request.form.get("subject", "").strip()
        template_name = request.form.get("template", "welcome")
        name = request.form.get("name", "there").strip() or "there"
        offer = request.form.get("offer", "25% OFF").strip() or "25% OFF"
        if template_name not in ("welcome", "promotion", "newsletter"):
            flash("Please choose a valid email template.")
            return redirect(url_for("send_html_email"))
        try:
            validate_email(recipient, check_deliverability=False)
            if not subject:
                raise ValueError("Email subject is required.")
            if not settings.get("smtp_login") or not settings.get("smtp_key") or not settings.get("sender_email"):
                raise ValueError("Save your Brevo SMTP settings first.")
            html_body = render_template(f"emails/{template_name}.html", name=name, offer=offer)
            message = EmailMessage()
            message["Subject"] = subject
            message["From"] = f'{settings.get("sender_name", "MailStudio Pro")} <{settings["sender_email"]}>'
            message["To"] = recipient
            message.set_content(f"Hello {name},\n\nThis email contains an HTML version. If you cannot view it, open it in an HTML-capable email client.")
            message.add_alternative(html_body, subtype="html")
            context = ssl.create_default_context()
            with smtplib.SMTP("smtp-relay.brevo.com", 587, timeout=25) as server:
                server.ehlo()
                server.starttls(context=context)
                server.ehlo()
                server.login(settings["smtp_login"], settings["smtp_key"])
                server.send_message(message)
            flash(f"HTML email accepted by Brevo for {recipient}. Check Inbox and Spam.")
        except (EmailNotValidError, ValueError, smtplib.SMTPException, OSError) as exc:
            flash(f"HTML email could not be sent: {exc}")
        return redirect(url_for("send_html_email"))
    return render_template("send_html.html")

@app.route("/health")
def health(): return jsonify({"status":"ok","app":"Email Developer Suite","mode":"local demo"})

if __name__ == "__main__":
    init_db()
    app.run(debug=True, port=5000)
