import requests
import logging
from app.config.settings import settings

logger = logging.getLogger("VVResidencyAPI")

HOTEL_NAME    = "VV Residency"
HOTEL_ADDRESS = "123 Grand Boulevard, Opp. Medical College, Chennai, Tamil Nadu – 600001"
HOTEL_PHONE   = "73395 06878"
HOTEL_GSTIN   = "33AAHPB1964D1Z9"

BREVO_API_URL = "https://api.brevo.com/v3/smtp/email"


def send_booking_confirmation(booking: dict):
    """
    Sends a booking confirmation email with a digital receipt to the guest.
    Uses Brevo Transactional Email API (HTTPS POST — no SMTP, works on Render).
    Reads BREVO_API_KEY and SENDER_EMAIL from application settings.
    """
    api_key      = (settings.BREVO_API_KEY or "").strip()
    sender_email = (settings.SENDER_EMAIL  or "").strip()

    logger.info(f"[EMAIL] BREVO_API_KEY Loaded: {bool(api_key)}")
    logger.info(f"[EMAIL] SENDER_EMAIL  Loaded: {bool(sender_email)}")

    if not api_key:
        msg = "Email service is not configured: BREVO_API_KEY environment variable is missing."
        logger.warning(msg)
        raise ValueError(msg)

    if not sender_email:
        msg = "Email service is not configured: SENDER_EMAIL environment variable is missing."
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
    checkout    = booking.get("checkout",    "")
    amount      = booking.get("amount",      0)

    bill_display = f"Bill No: {bill_number}" if bill_number else f"Booking ID: {booking_id}"
    subject      = f"Booking Confirmation — {HOTEL_NAME} ({booking_id})"

    # ── Plain text ────────────────────────────────────────────────────
    text_content = f"""
Dear {guest_name},

Thank you for choosing {HOTEL_NAME}. Your booking is confirmed!

{bill_display}
Booking ID   : {booking_id}
Room         : {room_id} — {room_name}
Check-in     : {checkin}
Check-out    : {checkout}
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
    <div class="logo">VV</div>
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
    <div>Arrival Date : <strong>{checkin}</strong></div>
    <div style="text-align:center;">Room No: <strong>{room_id}</strong></div>
    <div style="text-align:right;">Departure Date : <strong>{checkout}</strong></div>
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
    <span class="paid-tag">RECEIVED PAID</span>
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

    # ── Call Brevo Transactional Email API ────────────────────────────
    payload = {
        "sender":      {"name": HOTEL_NAME, "email": sender_email},
        "to":          [{"email": guest_email, "name": guest_name}],
        "subject":     subject,
        "htmlContent": html_content,
        "textContent": text_content,
    }

    headers = {
        "accept":       "application/json",
        "content-type": "application/json",
        "api-key":      api_key,
    }

    logger.info(f"[EMAIL] Calling Brevo API for booking={booking_id}, to={guest_email}")
    try:
        response = requests.post(BREVO_API_URL, json=payload, headers=headers, timeout=15)
        status_code = response.status_code
        logger.info(f"[EMAIL] Brevo API response: HTTP {status_code} — {response.text[:200]}")

        if status_code not in (200, 201):
            error_body = response.text
            logger.error(f"[EMAIL] Brevo API rejected the request: {error_body}")
            raise RuntimeError(
                f"Brevo API returned HTTP {status_code}: {error_body}"
            )

        logger.info(f"[EMAIL] Email sent successfully to {guest_email} via Brevo API.")
        return response.json()

    except requests.exceptions.Timeout:
        logger.exception("[EMAIL] Brevo API request timed out after 15 s.")
        raise RuntimeError("Brevo API request timed out. Please try again.")
    except requests.exceptions.RequestException as e:
        logger.exception(f"[EMAIL] Network error calling Brevo API: {e}")
        raise RuntimeError(f"Network error sending email: {e}")