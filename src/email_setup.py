import logging
import os
import smtplib
from email.message import EmailMessage

logger = logging.getLogger(__name__)

EMAIL_USER = os.getenv("EMAIL_USER")
EMAIL_PASS = os.getenv("EMAIL_PASS")
EMAIL_TO   = os.getenv("EMAIL_TO", EMAIL_USER)

def send_alert(breach_time, breach_value, plot_path):
    msg = EmailMessage()

    time_str = breach_time.strftime('%Y-%m-%d %H:%M:%S')
    msg.set_content(
        f"Waterstand alarm!\n\n"
        f"De drempelwaarde is overschreden.\n\n"
        f"Eerste moment van overschrijding: {time_str} UTC+1\n"
        f"Verwacht peil: {breach_value} cm +NAP.\n\n"
        f"Zie de bijgevoegde grafiek voor de volledige verwachting."
    )

    msg['Subject'] = f"Waterpeil Alarm: {breach_value}cm om {breach_time.strftime('%H:%M')}"
    msg['From'] = f"Watermelder <{EMAIL_USER}>"
    msg['To'] = EMAIL_TO

    if plot_path and os.path.exists(plot_path):
        with open(plot_path, 'rb') as f:
            msg.add_attachment(f.read(), maintype='image', subtype='png', filename=os.path.basename(plot_path))
        logger.info("Attached forecast plot from %s", plot_path)
    else:
        logger.warning("No plot attachment found at %s", plot_path)

    logger.info("Sending alert email to %s", EMAIL_TO)
    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(EMAIL_USER, EMAIL_PASS)
            server.send_message(msg)
        logger.info("Alert email sent")
    except Exception as e:
        logger.error("Failed to send alert email: %s", e)
