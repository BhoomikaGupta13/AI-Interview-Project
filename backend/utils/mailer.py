# backend/utils/mailer.py

import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dotenv import load_dotenv

load_dotenv()


def send_welcome_email(
    candidate_email: str, full_name: str, username: str, password_plain: str
) -> bool:
    """
    Dispatches a professional recruitment onboard invitation email to the candidate
    containing system authentication credentials.
    """
    # 1. Gather configuration metrics securely using your exact .env keys
    smtp_server = os.getenv("SMTP_SERVER", "smtp.gmail.com")
    smtp_port = int(os.getenv("SMTP_PORT", 465))

    # ── UPDATED TO MATCH YOUR EXPICIT .ENV NAMES ─────────────────────────────
    smtp_user = os.getenv("GMAIL_SENDER")  # Changed from SMTP_USER
    smtp_password = os.getenv("GMAIL_APP_PASSWORD")

    if not smtp_user or not smtp_password:
        print("[Mailer Error] Missing SMTP configuration flags in your .env file.")
        return False

    # 2. Build Multi-part MIME Container layout
    msg = MIMEMultipart("alternative")
    msg["Subject"] = "🚀 Invitation: Automated AI Technical Interview Portal"
    msg["From"] = f"AI Recruitment Board <{smtp_user}>"
    msg["To"] = candidate_email

    # 3. Create clean professional HTML template message content
    html_content = f"""
    <html>
        <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333333; max-width: 600px; margin: 0 auto; padding: 20px;">
            <div style="background-color: #1a1c23; padding: 20px; border-radius: 8px 8px 0 0; text-align: center; color: #ffffff;">
                <h2 style="margin: 0; color: #3182ce;">AI Technical Interview invitation</h2>
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

                <h4 style="color: #2d3748; margin-bottom: 8px;">⚠️ Key Compliance Instructions:</h4>
                <ul style="padding-left: 20px; margin-top: 0; color: #4a5568;">
                    <li>Ensure your **Webcam** and **Microphone** devices are functional before starting.</li>
                    <li>Please maintain a clear speaking voice; an on-screen **Live Input Audio Graph** will assist you.</li>
                    <li>Do not leave the fullscreen window frame or swap browser tabs during the active testing window; doing so flags proctoring violations and will lock your session.</li>
                </ul>
                
                <p style="margin-top: 25px;">Best of luck with your evaluation process!</p>
                <hr style="border: none; border-top: 1px solid #e2e8f0; margin: 20px 0;" />
                <p style="font-size: 11px; color: #a0aec0; text-align: center; margin: 0;">This is an automated operational notification link message. Please do not reply directly.</p>
            </div>
        </body>
    </html>
    """

    msg.attach(MIMEText(html_content, "html"))

    # 4. Initiate Secure SSL SMTP Handshake Connection execution
    try:
        with smtplib.SMTP_SSL(smtp_server, smtp_port) as server:
            server.login(smtp_user, smtp_password)
            server.sendmail(smtp_user, candidate_email, msg.as_string())
        print(f"[Mailer] Access dispatch successfully sent to {candidate_email}")
        return True
    except Exception as mail_error:
        print(f"[Mailer Error] Secure communication dispatch failed: {mail_error}")
        return False
