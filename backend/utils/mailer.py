# backend/utils/mailer.py

import os
import dns.resolver
import smtplib
import socket
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dotenv import load_dotenv
from email_validator import validate_email, EmailNotValidError

load_dotenv()


def _smtp_mailbox_probe(
    email: str, from_address: str = "probe@check.local"
) -> tuple[bool, str]:
    """
    Stage 3: SMTP RCPT probe — connects directly to the recipient domain's
    mail server and asks "does this mailbox exist?" without sending any mail.

    How it works:
      1. Look up the domain's MX record to find its mail server hostname.
      2. Open a raw SMTP connection to port 25 on that server.
      3. Send EHLO -> MAIL FROM -> RCPT TO and read the response code.
         - 250 / 251  -> mailbox confirmed to exist
         - 550 / 551 / 553 -> mailbox does not exist
         - Anything else (421, 450, 452, connection refused, timeout) ->
           the server is greylisting or blocking probes; we return
           (True, "") so we don't false-block real addresses.

    IMPORTANT CAVEATS:
      - Gmail, Outlook, Yahoo and most large providers return 250 for ALL
        addresses regardless (catch-all / anti-harvest policy). This probe
        is most effective against smaller / corporate mail servers.
      - A timeout or refused connection is treated as "unknown, allow through"
        to avoid false positives on legitimate addresses.

    Returns: (is_valid: bool, reason: str)
      is_valid=True  + reason=""    -> exists or indeterminate (allow)
      is_valid=False + reason="..." -> server explicitly rejected the mailbox
    """
    domain = email.split("@")[1]

    # 1. Resolve MX record
    try:
        mx_records = sorted(
            dns.resolver.resolve(domain, "MX"), key=lambda r: r.preference
        )
        mx_host = str(mx_records[0].exchange).rstrip(".")
    except Exception:
        # Can't resolve MX — already caught in Stage 2; allow through here
        return True, ""

    # 2. Open raw SMTP connection to port 25
    try:
        with smtplib.SMTP(timeout=10) as smtp:
            smtp.connect(mx_host, 25)
            smtp.ehlo_or_helo_if_needed()
            smtp.mail(from_address)
            code, _ = smtp.rcpt(email)

            if code in (250, 251):
                return True, ""  # Mailbox confirmed
            elif code in (550, 551, 552, 553, 554):
                return False, (
                    f"The email address '{email}' does not exist or is not "
                    "accepting mail. Please provide a valid, active inbox."
                )
            else:
                # Greylisted / rate-limited / catch-all — don't block
                return True, ""
    except (
        smtplib.SMTPConnectError,
        smtplib.SMTPServerDisconnected,
        socket.timeout,
        OSError,
    ):
        # Server refused our probe connection — treat as indeterminate, allow
        return True, ""


def validate_candidate_email(email: str) -> tuple[bool, str]:
    """
    Three-stage email validation pipeline:

      Stage 1 - Syntax  (no network)  : catches "user@", "plaintext", "a@b"
      Stage 2 - DNS/MX  (DNS lookup)  : catches fake domains like notreal.xyz
      Stage 3 - SMTP probe (port 25)  : catches non-existent mailboxes on
                                        servers that respond honestly (most
                                        corporate / smaller providers).
                                        Large providers (Gmail/Outlook/Yahoo)
                                        use catch-all policies, so a fake Gmail
                                        address will still pass Stage 3 — this
                                        is a known provider-side limitation and
                                        cannot be worked around without a paid
                                        verification API (ZeroBounce, NeverBounce).

    Returns:
      (True,  normalised_email)  -> address passed all stages, safe to send
      (False, user_facing_error) -> address rejected, show this to the admin
    """
    clean = email.strip()

    # Stage 1: Syntax only (fast, no network call)
    try:
        validate_email(clean, check_deliverability=False)
    except EmailNotValidError:
        return False, (
            "The email address format is invalid. "
            "Please enter a valid address like name@domain.com."
        )

    # Stage 2: DNS / MX record check
    try:
        email_info = validate_email(clean, check_deliverability=True)
        normalised = email_info.normalized
    except EmailNotValidError:
        domain = clean.split("@")[-1] if "@" in clean else clean
        return False, (
            f"The email domain '{domain}' does not exist or cannot receive mail. "
            "Please enter a real, active email address."
        )

    # Stage 3: SMTP RCPT probe (catches non-existent mailboxes where servers cooperate)
    probe_ok, probe_error = _smtp_mailbox_probe(normalised)
    if not probe_ok:
        return False, probe_error

    return True, normalised


def send_welcome_email(
    candidate_email: str, full_name: str, username: str, password_plain: str
) -> tuple[bool, str]:
    """
    Validates email deliverability and dispatches account credentials.
    Returns: (bool_success, string_status_message)
    """
    # 1. Three-stage validation before attempting any SMTP work
    is_valid, result = validate_candidate_email(candidate_email)
    if not is_valid:
        print(f"[Mailer] Validation blocked send: {result}")
        return False, result

    # result now holds the normalised email address
    clean_email = result

    # 2. Gather SMTP configuration from .env
    smtp_server = os.getenv("SMTP_SERVER", "smtp.gmail.com")
    smtp_port = int(os.getenv("SMTP_PORT", 465))
    smtp_user = os.getenv("GMAIL_SENDER")
    smtp_password = os.getenv("GMAIL_APP_PASSWORD")

    if not smtp_user or not smtp_password:
        return False, "Missing SMTP configuration flags in your .env file."

    # 3. Build Multi-part MIME message
    msg = MIMEMultipart("alternative")
    msg["Subject"] = "🚀 Invitation: Automated AI Technical Interview Portal"
    msg["From"] = f"AI Recruitment Board <{smtp_user}>"
    msg["To"] = clean_email

    html_content = f"""
    <html>
        <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333333; max-width: 600px; margin: 0 auto; padding: 20px;">
            <div style="background-color: #1a1c23; padding: 20px; border-radius: 8px 8px 0 0; text-align: center; color: #ffffff;">
                <h2 style="margin: 0; color: #3182ce;">AI Technical Interview Invitation</h2>
            </div>
            <div style="background-color: #f7fafc; padding: 20px; border: 1px solid #e2e8f0; border-top: none; border-radius: 0 0 8px 8px;">
                <p>Hello <strong>{full_name}</strong>,</p>
                <p>You have been formally registered by the recruitment administrator to undergo an automated technical assessment platform round on our AI system.</p>
                
                <div style="background-color: #ffffff; padding: 15px; border-radius: 6px; border: 1px solid #cbd5e0; margin: 20px 0;">
                    <h4 style="margin-top: 0; color: #2d3748; border-bottom: 1px solid #e2e8f0; padding-bottom: 8px;">🔑 Your Access Credentials</h4>
                    <table style="width: 100%; border-collapse: collapse;">
                        <tr>
                            <td style="padding: 5px 0; color: #4a5568; font-weight: bold; width: 35%;">Portal Link:</td>
                            <td style="padding: 5px 0; color: #2b6cb0;">http://localhost:8501 (Candidate View)</td>
                        </tr>
                        <tr>
                            <td style="padding: 5px 0; color: #4a5568; font-weight: bold;">Login ID (Username):</td>
                            <td style="padding: 5px 0;"><code style="background-color: #edf2f7; padding: 2px 6px; border-radius: 4px; font-weight: bold; color: #c53030;">{username}</code></td>
                        </tr>
                        <tr>
                            <td style="padding: 5px 0; color: #4a5568; font-weight: bold;">Temporary Password:</td>
                            <td style="padding: 5px 0;"><code style="background-color: #edf2f7; padding: 2px 6px; border-radius: 4px; font-weight: bold; color: #c53030;">{password_plain}</code></td>
                        </tr>
                    </table>
                </div>
                <p style="margin-top: 25px;">Best of luck with your evaluation process!</p>
            </div>
        </body>
    </html>
    """
    msg.attach(MIMEText(html_content, "html"))

    try:
        with smtplib.SMTP_SSL(smtp_server, smtp_port) as server:
            server.login(smtp_user, smtp_password)
            server.sendmail(smtp_user, clean_email, msg.as_string())
        return True, "Invitation credentials successfully routed to candidate inbox."
    except Exception as mail_error:
        return False, f"SMTP relay connection drop error: {str(mail_error)}"
