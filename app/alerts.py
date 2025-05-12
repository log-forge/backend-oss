import time
from datetime import datetime
from pathlib import Path
import subprocess
import yaml
from .docker_utils import create_docker_dict, CONTAINER_DICT, client
from .send_email import send_email_alert
from datetime import datetime, timedelta, timezone
import hashlib
import re

# In-memory alert list (can move to file/db later)
ALERT_STORE = []

# Prevent spamming: store last alert time per container
ALERT_CACHE = {}

ALERT_START_CACHE = {}

EMAIL_MESSAGE_CACHE = {}  # container -> { message: timestamp }


CONFIG_PATH = Path(__file__).parent / "config.yml"
COOLDOWN_SECONDS = 300  # default if not in config


def load_config_keywords_and_cooldown():
    with open(CONFIG_PATH, "r") as f:
        config = yaml.safe_load(f)
    keywords = config.get("alert", {}).get("keywords", [])
    cooldown = config.get("alert", {}).get("cooldown_seconds", COOLDOWN_SECONDS)
    interval_hours = config.get("email", {}).get("alert_interval_hours", 1)
    return keywords, cooldown, interval_hours


def scan_logs_for_alerts():

    cutoff = datetime.now(timezone.utc) - timedelta(hours=48)
    ALERT_STORE[:] = [
        alert for alert in ALERT_STORE
        if datetime.fromisoformat(alert["timestamp"]) > cutoff
    ]

    create_docker_dict()
    reset_alerts_on_container_rebuild()
    keywords, cooldown, interval_hours = load_config_keywords_and_cooldown()
    now = time.time()

    for name, data in CONTAINER_DICT.items():
        container_id = data["container_id"]
        # cooldown check
        last_alert = ALERT_CACHE.get(name, 0)
        if now - last_alert < cooldown:
            continue

        # get last 3 minute logs

        logs = client.containers.get(container_id).logs(
            since=int(time.time()) - 180,  # last 3 minutes
            timestamps=False,
            stream=True,
            follow=False,
        )
        for line in logs:
            line = line.decode(errors="ignore")
            if any(k in line for k in keywords):
                msg = line.strip()
                nodt_msg = strip_leading_timestamp(msg)
                hashed_msg = hash_message(nodt_msg)
                last_sent_time = EMAIL_MESSAGE_CACHE.get(hashed_msg)
                print(f"[DEBUG] {name} - {hashed_msg} - {last_sent_time}")
                if not last_sent_time:
                    ALERT_STORE.append({
                        "container": name,
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "message": msg,
                    })

                    send_email_alert(
                        container=name,
                        subject=f"🚨 LogForge Alert in {name}",
                        body=f"Keyword matched in logs at {datetime.now(timezone.utc).isoformat()}.\n\nLine:\n{line.strip()}"
                    )
                EMAIL_MESSAGE_CACHE[hashed_msg] = datetime.now(timezone.utc)



                break  # 1 alert per container per cycle

def reset_alerts_on_container_rebuild():
    """
    Check for containers that were restarted or rebuilt,
    and clear any existing alerts for those containers.

    This compares the current 'StartedAt' time with the last known time
    in ALERT_START_CACHE, and resets ALERT_STORE entries if they changed.
    """
    for name, data in CONTAINER_DICT.items():
        started_at = data.get("started_at")
        last_start = ALERT_START_CACHE.get(name)

        if last_start and last_start != started_at:
            # Container was rebuilt → remove its old alerts
            ALERT_STORE[:] = [a for a in ALERT_STORE if a["container"] != name]

        # Update known start time
        ALERT_START_CACHE[name] = started_at

def hash_message(msg: str) -> str:
    return hashlib.sha256(msg.encode("utf-8")).hexdigest()

def strip_leading_timestamp(msg: str) -> str:
    # Common patterns like:
    # 2025-05-09T00:16:16.278363799Z
    # Fri May 9 00:16:16 UTC 2025:
    # 2025-05-09 00:16:16,123
    msg = msg.strip()

    # Remove ISO format or syslog-style timestamp at the beginning
    cleaned = re.sub(
        r"""^(?:
            \d{4}-\d{2}-\d{2}[T\s]\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z| UTC)?   # ISO 8601 / Docker / UTC
            |
            [A-Za-z]{3} \s[A-Za-z]{3} \s+\d{1,2} \d{2}:\d{2}:\d{2}(?:\sUTC)?\s\d{4}  # Fri May 9 00:16:16 UTC 2025
        )[:\s-]*""",
        "",
        msg,
        flags=re.VERBOSE
    )
    return cleaned.strip()