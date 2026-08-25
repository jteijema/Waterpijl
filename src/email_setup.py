import logging
import os
import smtplib
from email.message import EmailMessage

from jinja2 import Environment, FileSystemLoader

logger = logging.getLogger(__name__)

EMAIL_USER = os.getenv("EMAIL_USER")
EMAIL_PASS = os.getenv("EMAIL_PASS")
EMAIL_TO   = os.getenv("EMAIL_TO", EMAIL_USER)

REPO_ROOT           = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EMAIL_TEMPLATE_FILE = os.getenv("EMAIL_TEMPLATE_FILE", os.path.join(REPO_ROOT, "email_template.txt"))

_env      = Environment(loader=FileSystemLoader(os.path.dirname(EMAIL_TEMPLATE_FILE)))
_template = _env.get_template(os.path.basename(EMAIL_TEMPLATE_FILE))


def _render_email(breach_time, breach_value):
    rendered = _template.render(breach_time=breach_time, breach_value=breach_value)
    subject, _, body = rendered.partition("\n\n")
    subject = subject.partition(":")[2].strip()
    return subject, body


def send_alert(breach_time, breach_value, plot_path):
    msg = EmailMessage()
    subject, body = _render_email(breach_time, breach_value)
    msg.set_content(body)
    msg['Subject'] = subject
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
