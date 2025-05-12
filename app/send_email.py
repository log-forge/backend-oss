import yaml
import yagmail
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

EMAIL_INTERVAL_CACHE = {}  # email -> container

def get_config():
    """Load and return the configuration file."""
    CONFIG_PATH = Path(__file__).parent / "config.yml"
    with open(CONFIG_PATH, "r") as f:
        return yaml.safe_load(f)

def should_send_email(container: str) -> bool:
    """Check if an email should be sent based on the interval.

    Args:
        container (str): The container name.

    Returns:
        bool: True if an email should be sent, False otherwise.
    """
    config = get_config()
    email_config = config.get("email", {})
    interval_hours = email_config.get("alert_interval_hours", 1)
    email_recipients = email_config.get("recipients", {})
    interval_secs = interval_hours * 3600

    now = time.time()

    if container not in EMAIL_INTERVAL_CACHE:
        EMAIL_INTERVAL_CACHE[container] = (email_recipients.get(container, []), now)
        return True
    
    else:
        last_sent = EMAIL_INTERVAL_CACHE[container][1]
        if now - last_sent >= interval_secs:
            EMAIL_INTERVAL_CACHE[container] = (email_recipients.get(container, []), now)
            return True
        else:
            return False





def send_email_alert(container: str, subject: str, body: str):
    """Send an email alert to recipients based on the container.

    Args:
        container (str): The container name triggering the alert.
        subject (str): The subject of the email.
        body (str): The body content of the alert.
    """
    if not should_send_email(container):
        return

    CONFIG_PATH = Path(__file__).parent / "config.yml"
    with open(CONFIG_PATH, "r") as f:
        config = yaml.safe_load(f)

    email_cfg = config.get("email", {})
    if not email_cfg.get("enabled"):
        return

    sender = email_cfg.get("sender")
    password = email_cfg.get("app_password")
    recipients_map = email_cfg.get("recipients", {})

    # Get specific or fallback recipients
    to_emails = recipients_map.get(container, recipients_map.get("default", []))
    if not to_emails:
        return  # No recipients to send to

    yag = yagmail.SMTP(sender, password)
    yag.send(to=to_emails, subject=subject, contents=body)