# Email Developer Suite — Portfolio Project

A local, working portfolio application demonstrating HTML email development workflows:
- responsive, table-based HTML email templates
- personalized preview with fallback values
- contact management and CSV import
- audience segmentation and consent tracking
- campaign draft management
- QA checklist
- A/B test planning (planning only; no campaign is sent)
- basic campaign/audience reporting

## Run on Windows
1. Install Python 3.10+.
2. Extract this ZIP.
3. Double-click `run_windows.bat`.
4. Open `http://127.0.0.1:5000`.

The first run creates `data/email_suite.db` and sample contacts.

## Important truth about sending
This project creates and previews campaigns locally. It does **not** send real marketing emails. Before any real deployment, connect an approved provider (e.g. Salesforce Marketing Cloud, Braze, Adobe Campaign, or a properly configured SMTP/email service), obtain consent, configure SPF/DKIM/DMARC, add a working unsubscribe mechanism, and test rendering in real email clients.

## Demo credentials
No login is configured; keep this local and do not expose it publicly.

## CSV import format
Required headers: `name,email`
Optional headers: `city,segment,consent`
Consent values accepted: `1/0`, `true/false`, `yes/no`.

## Suggested interview walkthrough
1. Dashboard and project architecture.
2. Add/import a contact and filter by segment.
3. Create a campaign draft.
4. Open personalized preview.
5. Run the QA checklist and explain the items requiring live infrastructure.
6. Create an A/B test plan.
7. Show reports and explain consent/data hygiene.

## Project structure
- `app.py` — Flask routes, SQLite persistence, validation
- `templates/` — dashboard and management UI
- `templates/emails/` — standalone HTML email templates
- `static/css/` — application styling
- `data/` — local SQLite database (created on first run)


## Brevo SMTP integration (real test email)
1. In Brevo, open Settings → SMTP & API → SMTP and generate an SMTP key.
2. Verify the sender email address in Brevo.
3. Start MailStudio Pro and open Brevo SMTP in the sidebar.
4. Enter SMTP login, SMTP key, and verified sender email. Host: smtp-relay.brevo.com; port: 587.
5. Save settings and send a test email to your own inbox.

The SMTP key is stored locally in `brevo_settings.json`. Keep it private; do not upload or commit it. The separate Brevo API key is not needed for this SMTP test feature. This adds individual test-email sending, not bulk campaign delivery or Gmail/Outlook rendering tests.


## Send a real HTML email
After saving Brevo SMTP settings and verifying your sender, open **Send HTML email** in the sidebar. Choose Welcome, Promotion, or Newsletter, enter your own recipient email and subject, then send. The app sends a multipart message with a plain-text fallback and responsive HTML body through Brevo SMTP over TLS. Start with your own inbox and send only to people who consented. This is single-recipient sending, not bulk campaign delivery.
