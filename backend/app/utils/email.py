import logging
import smtplib
from email.header import Header
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formataddr

from app.config.settings import settings

logger = logging.getLogger("VVResidencyAPI")

HOTEL_NAME = settings.HOTEL_NAME
HOTEL_ADDRESS = settings.HOTEL_ADDRESS
HOTEL_PHONE = settings.HOTEL_PHONE
HOTEL_GSTIN = settings.HOTEL_GSTIN


def send_booking_confirmation(booking: dict):
    """
    Sends a booking confirmation email with a digital receipt to the guest.
    Uses Gmail SMTP (STARTTLS on port 587) with Google App Password.
    Reads SENDER_EMAIL and GMAIL_APP_PASSWORD from application settings.
    """
    app_password = (settings.GMAIL_APP_PASSWORD or "").strip().replace(" ", "")
    sender_email = (settings.SENDER_EMAIL or "").strip()

    logger.info(f"[EMAIL] GMAIL_APP_PASSWORD Loaded: {bool(app_password)}")
    logger.info(f"[EMAIL] SENDER_EMAIL       Loaded: {bool(sender_email)}")

    if not sender_email:
        msg = "Email service is not configured: SENDER_EMAIL environment variable is missing."
        logger.warning(msg)
        raise ValueError(msg)

    if not app_password:
        msg = "Email service is not configured: GMAIL_APP_PASSWORD environment variable is missing."
        logger.warning(msg)
        raise ValueError(msg)

    guest_email = booking.get("guest_email")
    if not guest_email:
        msg = "Guest email address is missing from booking data."
        logger.error(msg)
        raise ValueError(msg)

    guest_name  = booking.get("guest_name",  "Guest")
    booking_id  = booking.get("booking_id",  "Unknown")
    bill_number = booking.get("bill_number", "")
    room_id     = booking.get("room_id",     "")
    room_name   = booking.get("room_name",   f"Room {room_id}")
    checkin     = booking.get("checkin",     "")
    ci_time     = booking.get("checkin_time", "12:00") or "12:00"
    checkout    = booking.get("checkout",    "")
    co_time     = booking.get("checkout_time", "11:00") or "11:00"
    amount      = booking.get("amount",      0)

    bill_display = f"Bill No: {bill_number}" if bill_number else f"Booking ID: {booking_id}"
    subject      = f"Booking Confirmation — {HOTEL_NAME} ({booking_id})"
    words        = [w for w in HOTEL_NAME.strip().split() if w]
    if not words:
        hotel_initials = "HM"
    elif words[0].isupper() and len(words[0]) <= 3:
        hotel_initials = words[0]
    elif len(words) >= 2:
        hotel_initials = (words[0][0] + words[1][0]).upper()
    else:
        hotel_initials = words[0][:2].upper()

    # ── Plain text ────────────────────────────────────────────────────
    text_content = f"""
Dear {guest_name},

Thank you for choosing {HOTEL_NAME}. Your booking is confirmed!

{bill_display}
Booking ID   : {booking_id}
Room         : {room_id} — {room_name}
Check-in     : {checkin} at {ci_time}
Check-out    : {checkout} at {co_time}
Total Amount : ₹{amount:,.0f}

{HOTEL_ADDRESS}
Phone: {HOTEL_PHONE}
GSTIN: {HOTEL_GSTIN}

Thank You. Come Again.

Best regards,
{HOTEL_NAME} Team
"""

    # ── HTML receipt ──────────────────────────────────────────────────
    html_content = f"""
<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<style>
  body {{ font-family: Arial, sans-serif; background:#f4f4f4; margin:0; padding:20px; }}
  .receipt {{
    max-width: 600px; margin: 0 auto;
    background: #FBF0C8;
    border: 3px solid #9B1B30;
    color: #7A1428;
    padding: 24px;
  }}
  .header {{ border-bottom: 3px solid #9B1B30; padding-bottom: 12px; margin-bottom: 12px; display: flex; align-items: center; gap: 12px; }}
  .logo {{ width:46px; height:46px; border: 2.5px solid #9B1B30; border-radius:50%; display:flex; align-items:center; justify-content:center; font-weight:700; font-size:1.1rem; color:#9B1B30; }}
  .brand {{ font-size: 1.6rem; font-weight: 700; color: #9B1B30; }}
  .brand span {{ font-size: 0.9rem; letter-spacing:1px; display:block; }}
  .topline {{ display:flex; justify-content:space-between; font-size:0.8rem; margin-bottom:8px; }}
  .addr {{ font-size:0.8rem; line-height:1.5; margin-bottom:10px; }}
  .section {{ border-top: 2px solid #9B1B30; border-bottom: 2px solid #9B1B30; display:grid; grid-template-columns:1fr 1fr; margin-bottom:10px; }}
  .col {{ padding: 10px 14px; }}
  .col-left {{ border-right: 2px solid #9B1B30; }}
  .row {{ display:flex; justify-content:space-between; font-size:0.84rem; padding: 4px 0; }}
  .row b {{ min-width:70px; text-align:right; }}
  .total {{ display:flex; justify-content:space-between; font-weight:700; font-size:0.9rem; border-top:1.5px solid #9B1B30; margin-top:6px; padding-top:6px; }}
  .paid-tag {{ background:#9B1B30; color:#FBF0C8; font-weight:700; padding:4px 14px; border-radius:4px; font-size:0.78rem; }}
  .footer-row {{ display:flex; justify-content:space-between; margin-top:14px; font-size:0.8rem; }}
  .thanks {{ font-size:1rem; font-style:italic; }}
</style>
</head>
<body>
<div class="receipt">
  <div class="topline">
    <span>GSTIN: {HOTEL_GSTIN}</span>
    <span style="text-align:right;">{bill_display}<br>Booking ID: {booking_id}</span>
  </div>
  <div class="header">
    <div class="logo">{hotel_initials}</div>
    <div class="brand">{HOTEL_NAME} <span>ROOMS</span></div>
  </div>
  <div class="addr">
    {HOTEL_ADDRESS}<br>
    &#128222; {HOTEL_PHONE}
  </div>
  <p style="font-size:0.88rem; margin-bottom:10px;">
    Name of the Customer Mr./Mrs./Ms. <strong>{guest_name}</strong>
  </p>
  <div style="font-size:0.84rem; margin-bottom:10px; display:grid; grid-template-columns:1.3fr 0.8fr 1.3fr; gap:6px;">
    <div>Arrival Date : <strong>{checkin}</strong><br>Time : <strong>{ci_time}</strong></div>
    <div style="text-align:center;">Room No: <strong>{room_id}</strong></div>
    <div style="text-align:right;">Departure Date : <strong>{checkout}</strong><br>Time : <strong>{co_time}</strong></div>
  </div>
  <div class="section">
    <div class="col col-left">
      <div class="row"><span>Rent</span><b>&#8377;{amount:,.0f}</b></div>
      <div class="row"><span>Phone Calls</span><b>&#8212;</b></div>
      <div class="row"><span>Sundries</span><b>&#8212;</b></div>
      <div class="row"><span>Service Charge</span><b>&#8212;</b></div>
      <div class="total"><span>Total :</span><span>&#8377;{amount:,.0f}</span></div>
    </div>
    <div class="col">
      <div class="row"><span>R. No.</span><b>{room_id}</b></div>
      <div class="row"><span>Advance</span><b>&#8212;</b></div>
      <div style="margin-top:10px; padding-top:10px; border-top:1px dashed #9B1B30; display:flex; justify-content:space-between;">
        <span>Bill Amount</span><strong>&#8377;{amount:,.0f}/-</strong>
      </div>
    </div>
  </div>
  <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:14px; font-size:0.85rem;">
    <span>Balance :</span>
    <span class="paid-tag">PAID</span>
  </div>
  <div style="font-size:0.7rem; line-height:1.7; margin-bottom:14px;">
    1. Cheques are not accepted.<br>
    2. Bill must be settled on presentation.<br>
    3. Only our official receipt is accepted.<br>
    4. We are not responsible for any cash or valuables missing after check-out.
  </div>
  <div class="footer-row">
    <span class="thanks">Thank You. Come Again.</span>
    <span style="text-align:center; font-size:0.78rem;">
      <span style="font-style:italic; font-size:1.1rem;">&#10003;</span><br>
      <span style="display:block; border-top:1.5px solid #9B1B30; width:120px; padding-top:2px;">For Manager</span>
    </span>
  </div>
</div>
</body>
</html>
"""

    # ── Compose MIME multipart email ──────────────────────────────────
    message = MIMEMultipart("alternative")
    message["Subject"] = subject
    message["From"] = formataddr((str(Header(HOTEL_NAME, "utf-8")), sender_email))
    message["To"] = formataddr((str(Header(guest_name, "utf-8")), guest_email))

    # Attach plain text and HTML alternative versions
    part_text = MIMEText(text_content, "plain", "utf-8")
    part_html = MIMEText(html_content, "html", "utf-8")
    message.attach(part_text)
    message.attach(part_html)

    # ── Send via Gmail SMTP ───────────────────────────────────────────
    logger.info(
        f"[EMAIL] Sending email via Gmail SMTP ({settings.SMTP_HOST}:{settings.SMTP_PORT}) "
        f"for booking={booking_id}, to={guest_email}"
    )

    try:
        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=20) as server:
            server.ehlo()
            server.starttls()
            server.ehlo()
            server.login(sender_email, app_password)
            server.sendmail(sender_email, [guest_email], message.as_string())

        logger.info(f"[EMAIL] Email sent successfully to {guest_email} via Gmail SMTP.")
        return {"status": "success", "message": f"Email sent to {guest_email}"}

    except smtplib.SMTPAuthenticationError as auth_err:
        logger.error(f"[EMAIL] Gmail SMTP authentication failed: {auth_err}")
        raise RuntimeError(
            "Gmail SMTP authentication failed. Please verify your SENDER_EMAIL and 16-character GMAIL_APP_PASSWORD in backend/.env."
        ) from auth_err
    except (smtplib.SMTPException, OSError) as smtp_err:
        logger.exception(f"[EMAIL] Error sending email via Gmail SMTP: {smtp_err}")
        raise RuntimeError(f"Failed to send email via Gmail SMTP: {smtp_err}") from smtp_err