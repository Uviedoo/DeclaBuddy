import os
import io
import uuid
import base64
import sqlite3
import threading
from datetime import datetime
from flask import Flask, render_template, request, send_file, flash, redirect, url_for, jsonify
from dotenv import load_dotenv
from apscheduler.schedulers.background import BackgroundScheduler
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
import filetype

# Database auto-update script
from setup_address_db import init_address_database

# Main engine
from PyPDFForm import PdfWrapper
import fitz  # PyMuPDF

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY")

# Set maximum upload size limit to 25 MB
app.config['MAX_CONTENT_LENGTH'] = 25 * 1024 * 1024

# Set up Rate Limiter
limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=["200 per day", "50 per hour"],
    storage_uri="memory://"
)

# Allowed file extensions & MIME types
ALLOWED_EXTENSIONS = {'pdf', 'png', 'jpg', 'jpeg', 'webp', 'tiff'}
ALLOWED_MIME_TYPES = {
    'application/pdf',
    'image/png',
    'image/jpeg',
    'image/webp',
    'image/tiff'
}

def is_allowed_file(file_storage) -> bool:
    """
    Validates both the filename extension AND the binary magic bytes (MIME type).
    """
    filename = file_storage.filename
    if not filename or '.' not in filename:
        return False

    # 1. Extension check
    ext = filename.rsplit('.', 1)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        return False

    # 2. Magic byte (MIME type) check
    header = file_storage.read(260)  # Read first 260 bytes to inspect file header
    file_storage.seek(0)             # CRITICAL: Reset file pointer for subsequent reading!

    kind = filetype.guess(header)
    if kind is None or kind.mime not in ALLOWED_MIME_TYPES:
        return False

    return True

# SECURITY HEADERS
@app.after_request
def set_security_headers(response):
    """Enforces standard security headers on all HTTP responses."""
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'SAMEORIGIN'
    response.headers['X-XSS-Protection'] = '1; mode=block'
    response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
    response.headers['Content-Security-Policy'] = (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline'; "
        "style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data:; "
        "font-src 'self';"
    )
    return response

# Handle HTTP 413 "Request Entity Too Large" errors cleanly
@app.errorhandler(413)
def request_entity_too_large(error):
    flash("Fout: De geüploade bestanden zijn te groot (maximaal 25 MB totaal).", "error")
    return redirect(url_for('claim_form'))

# Handle HTTP 429 "Rate Limit Exceeded" errors cleanly
@app.errorhandler(429)
def rate_limit_exceeded(error):
    flash("Te veel verzoeken! Probeer het later opnieuw.", "error")
    return redirect(url_for('claim_form'))

PDF_TEMPLATE_PATH = "claim_template.pdf"
DB_PATH = "addresses.db"
TEMP_DIR = os.path.join(os.getcwd(), "temp_uploads")
os.makedirs(TEMP_DIR, exist_ok=True)

# WEEKLY ADDRESS DATABASE AUTO-UPDATER
def run_address_db_check():
    """Triggers the weekly address database update check."""
    try:
        print("APScheduler: Checking address database for updates...")
        init_address_database()
    except Exception as e:
        print(f"APScheduler Error during address DB check: {e}")

scheduler = BackgroundScheduler(daemon=True)
scheduler.add_job(
    func=run_address_db_check, 
    trigger="interval", 
    days=7, 
    id="weekly_address_db_update",
    replace_existing=True
)

if os.environ.get('WERKZEUG_RUN_MAIN') == 'true' or not app.debug:
    scheduler.start()
    threading.Thread(target=run_address_db_check, daemon=True).start()

# NL data formatting
def format_date(date_str):
    if not date_str:
        return ""
    try:
        dt = datetime.strptime(date_str, "%Y-%m-%d")
        return dt.strftime("%d-%m-%Y")
    except ValueError:
        return date_str

def format_amount(amount_str):
    if not amount_str:
        return ""
    try:
        val = float(amount_str)
        return f"{val:.2f}".replace(".", ",")
    except ValueError:
        return amount_str

def flatten_and_sanitize_pdf(filled_bytes: bytes, receipt_files: list) -> bytes:
    """
    Refreshes visual appearance streams for form fields, bakes all widgets and images
    directly into static page vector graphics (/Contents), appends receipts (fitting images
    onto standard A4 pages), and purges all AcroForm metadata and scripts.
    """
    doc = fitz.open("pdf", filled_bytes)

    # 1. Force PyMuPDF to construct vector appearances for all filled fields
    for page in doc:
        for widget in page.widgets():
            widget.update()

    # 2. Append receipt uploads behind form pages
    for file in receipt_files:
        if file and file.filename != '':
            # Validate extension AND magic byte MIME type
            if not is_allowed_file(file):
                raise ValueError(f"Bestandstype of inhoud van '{file.filename}' is niet toegestaan.")

            file_bytes = file.read()
            filename_lc = file.filename.lower()

            if filename_lc.endswith('.pdf'):
                receipt_doc = fitz.open("pdf", file_bytes)
                doc.insert_pdf(receipt_doc)
                receipt_doc.close()

            elif filename_lc.endswith(('.png', '.jpg', '.jpeg', '.webp', '.tiff')):
                # Standard A4 dimensions in PDF points (210mm x 297mm)
                a4_width, a4_height = 595.32, 841.92
                margin = 20  # 20pt padding (~7mm)

                # Create a new A4 page
                a4_page = doc.new_page(width=a4_width, height=a4_height)

                # Define image display rectangle inside margins
                rect = fitz.Rect(margin, margin, a4_width - margin, a4_height - margin)

                # Fit image cleanly onto A4 page preserving aspect ratio
                a4_page.insert_image(rect, stream=file_bytes, keep_proportion=True)

    # 3. Bake form fields & annotations into background vector streams (/Contents)
    doc.bake(annots=True, widgets=True)

    output_bytes = doc.tobytes(deflate=True, garbage=4)
    doc.close()
    return output_bytes

# LOCAL HOSTED ADDRESS LOOKUP API
@app.route("/api/address-lookup", methods=["GET"])
@limiter.limit("30 per minute")  # Prevent address lookup API spamming
def api_address_lookup():
    postcode = request.args.get("postcode", "").replace(" ", "").upper()
    huisnummer = request.args.get("huisnummer", "").strip()

    if not postcode or not huisnummer:
        return jsonify({"success": False, "message": "Missing postcode or house number"}), 400

    if not os.path.exists(DB_PATH):
        return jsonify({"success": False, "message": "Address database missing"}), 500

    base_hnr = "".join(filter(str.isdigit, huisnummer)) or huisnummer

    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT straat, huisnummer, huisletter, huisnummertoevoeging, woonplaats
            FROM addresses
            WHERE postcode = ? AND huisnummer = ?
            LIMIT 1
        """, (postcode, base_hnr))

        row = cursor.fetchone()
        conn.close()

        if row:
            straat, hnr, hlet, htoev, woonplaats = row
            return jsonify({
                "success": True,
                "straat": straat,
                "woonplaats": woonplaats,
                "full_address": f"{straat} {huisnummer}"
            })
        else:
            return jsonify({"success": False, "message": "Address not found"}), 404

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/", methods=["GET", "POST"])
@limiter.limit("10 per minute", methods=["POST"])  # Limit form submissions to 10/min
def claim_form():
    if request.method == "POST":
        data_to_fill = {
            "Naam": request.form.get("Naam"),
            "Functie": request.form.get("Functie"),
            "Adres": request.form.get("Adres"),
            "Postcode": request.form.get("Postcode"),
            "Woonplaats": request.form.get("Woonplaats"),
            "Telefoon": request.form.get("Telefoon"),
            "E-mailadres": request.form.get("E-mailadres"),
            "IBAN": request.form.get("IBAN"),
            "Datum van indienen": format_date(request.form.get("Datum van indienen")),
            "OpmerkingenWijzigingen": request.form.get("OpmerkingenWijzigingen")
        }

        running_total = 0.0
        for i in range(1, 11):
            raw_date = request.form.get(f"Datum_transactie{i}", "")
            raw_amount = request.form.get(f"Bedrag{i}", "")

            if raw_amount:
                try:
                    running_total += float(raw_amount)
                except ValueError:
                    pass

            data_to_fill[f"Datum transactie{i}"] = format_date(raw_date)
            data_to_fill[f"Omschrijving{i}"] = request.form.get(f"Omschrijving{i}", "")
            data_to_fill[f"Bedrag{i}"] = format_amount(raw_amount)

        data_to_fill["Totaal"] = f"{running_total:.2f}".replace(".", ",")

        if not os.path.exists(PDF_TEMPLATE_PATH):
            flash("Fout: Sjabloon 'claim_template.pdf' ontbreekt in de hoofdmap.", "error")
            return redirect(url_for("claim_form"))

        temp_sig_path = None
        try:
            signature_data = request.form.get("Handtekening_data")
            if signature_data and "data:image/png;base64," in signature_data:
                img_data = signature_data.split(",")[1]
                temp_sig_path = os.path.join(TEMP_DIR, f"sig_{uuid.uuid4().hex}.png")
                with open(temp_sig_path, "wb") as fh:
                    fh.write(base64.b64decode(img_data))
                data_to_fill["Handtekening declarant_af_image"] = temp_sig_path

            # Step 1: Fill form fields & signature via PyPDFForm
            filled_form_bytes = PdfWrapper(PDF_TEMPLATE_PATH, need_appearances=True).fill(data_to_fill, flatten=False).read()

            receipt_files = request.files.getlist("Bijlagen")

            # Step 2: Validate extension + MIME, refresh appearances, append receipts, and bake fields into static graphics
            final_pdf_bytes = flatten_and_sanitize_pdf(filled_form_bytes, receipt_files)

            if temp_sig_path and os.path.exists(temp_sig_path):
                os.remove(temp_sig_path)

            output_filename = f"Declaratie_{data_to_fill['Naam'].replace(' ', '_')}.pdf"
            response = send_file(
                io.BytesIO(final_pdf_bytes),
                as_attachment=True,
                download_name=output_filename,
                mimetype="application/pdf"
            )
            # Prevent caching of personal claim documents
            response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
            response.headers['Pragma'] = 'no-cache'
            return response

        except Exception as e:
            if temp_sig_path and os.path.exists(temp_sig_path):
                os.remove(temp_sig_path)
            flash(f"Fout tijdens PDF-generatie: {str(e)}", "error")
            return redirect(url_for("claim_form"))

    return render_template("form.html")

if __name__ == "__main__":
    app.run(debug=False)