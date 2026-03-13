import smtplib
import os
from email.message import EmailMessage

EMAIL_USER = os.getenv("EMAIL_USER")
EMAIL_PASS = os.getenv("EMAIL_PASS")

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
    msg['To'] = f"{EMAIL_USER}, jelle@teije.ma"

    if plot_path and os.path.exists(plot_path):
        with open(plot_path, 'rb') as f:
            msg.add_attachment(f.read(), maintype='image', subtype='png', filename=os.path.basename(plot_path))

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(EMAIL_USER, EMAIL_PASS)
            server.send_message(msg)
        print("E-mail sent.")
    except Exception as e:
        print(f"E-mail fout: {e}")
