from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, EmailStr
import yaml
from pathlib import Path

router = APIRouter()

CONFIG_PATH = Path(__file__).parent.parent / "config.yml"


    
class KeywordUpdate(BaseModel):
    keywords: str

class RecipientUpdate(BaseModel):
    email: EmailStr
    container: str

class Passwordpdate(BaseModel):
    password: str

class SenderUpdate(BaseModel):
    email: EmailStr

@router.post("/config/filters/add-keyword")
def add_filter_keywords(body: KeywordUpdate):
    """
    Add multiple comma-separated alert keywords to config.yml.

    Args:
        body (KeywordUpdate): Comma-separated keywords string.

    Returns:
        dict: Success and skipped (already exists) lists.
    """
    try:
        new_keywords = [k.strip() for k in body.keywords.split(",") if k.strip()]
        with open(CONFIG_PATH, "r") as f:
            config = yaml.safe_load(f)

        config.setdefault("alert", {}).setdefault("keywords", [])
        existing = set(config["alert"]["keywords"])

        added = []
        for keyword in new_keywords:
            if keyword not in existing:
                config["alert"]["keywords"].append(keyword)
                added.append(keyword)

        with open(CONFIG_PATH, "w") as f:
            yaml.safe_dump(config, f)

        return {
            "status": "success",
            "added": added,
            "skipped": list(set(new_keywords) - set(added))
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    

    
@router.delete("/config/filters/remove-keyword")
def remove_alert_keyword(body: KeywordUpdate):
    """
    Remove a keyword from the alert keywords list in config.yml.

    Args:
        body (KeywordUpdate): JSON with the keyword to remove.

    Returns:
        dict: Success or not found message.
    """
    try:
        to_remove = [k.strip() for k in body.keywords.split(",") if k.strip()]
        with open(CONFIG_PATH, "r") as f:
            config = yaml.safe_load(f)

        config.setdefault("alert", {}).setdefault("keywords", [])
        original_keywords = config["alert"]["keywords"]

        removed = [k for k in to_remove if k in original_keywords]
        config["alert"]["keywords"] = [k for k in original_keywords if k not in to_remove]

        with open(CONFIG_PATH, "w") as f:
            yaml.safe_dump(config, f)

        return {
            "status": "success",
            "removed": removed,
            "not_found": list(set(to_remove) - set(removed))
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/config/filters")
def get_filter_keywords():
    """
    Get current list of alert keywords from config.yml.
    """
    try:
        with open(CONFIG_PATH, "r") as f:
            config = yaml.safe_load(f)

        return {
            "keywords": config.get("alert", {}).get("keywords", [])
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    

@router.post("/config/filters/replace")
def replace_filter_keywords(body: KeywordUpdate):
    """
    Replace the entire list of alert keywords in config.yml 
    with a new comma-separated set.

    Args:
        body (KeywordUpdate): Comma-separated keywords string.

    Returns:
        dict: List of new keywords that replaced the old list.
    """
    try:
        new_keywords = [k.strip() for k in body.keywords.split(",") if k.strip()]

        with open(CONFIG_PATH, "r") as f:
            config = yaml.safe_load(f)

        config.setdefault("alert", {})
        config["alert"]["keywords"] = new_keywords

        with open(CONFIG_PATH, "w") as f:
            yaml.safe_dump(config, f)

        return {
            "status": "success",
            "replaced_with": new_keywords
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
#------EMAIL------------
@router.post("/config/email/recipients/add")
def add_single_email(body: RecipientUpdate):
    try:
        with open(CONFIG_PATH, "r") as f:
            config = yaml.safe_load(f)

        config.setdefault("email", {}).setdefault("recipients", {})
        current = set(config["email"]["recipients"].get(body.container, []))

        if body.email not in current:
            current.add(body.email)
            config["email"]["recipients"][body.container] = list(current)

            with open(CONFIG_PATH, "w") as f:
                yaml.safe_dump(config, f)

            return {
                "status": "success",
                "added": body.email,
                "container": body.container
            }

        return {
            "status": "skipped",
            "reason": "email already present",
            "container": body.container
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
@router.post("/config/email/recipients/remove")
def remove_single_email(body: RecipientUpdate):
    try:
        with open(CONFIG_PATH, "r") as f:
            config = yaml.safe_load(f)

        recipients_map = config.setdefault("email", {}).setdefault("recipients", {})
        current = set(recipients_map.get(body.container, []))

        if body.email in current:
            current.remove(body.email)

            if current:
                recipients_map[body.container] = list(current)
            else:
                recipients_map.pop(body.container, None)

            with open(CONFIG_PATH, "w") as f:
                yaml.safe_dump(config, f)

            return {
                "status": "success",
                "removed": body.email,
                "container": body.container
            }

        return {
            "status": "skipped",
            "reason": "email not found",
            "container": body.container
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/config/email/recipients")
def get_email_recipients():
    try:
        with open(CONFIG_PATH, "r") as f:
            config = yaml.safe_load(f)

        recipients_raw = config.get("email", {}).get("recipients", {})

        return {
            container: {"recipients": emails}
            for container, emails in recipients_raw.items()
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/config/email/app_password")
def update_app_password(body: Passwordpdate):
    """
    Update the app password for sending emails.

    Args:
        body (RecipientUpdate): JSON with the new app password.

    Returns:
        dict: Success message.
    """
    try:
        with open(CONFIG_PATH, "r") as f:
            config = yaml.safe_load(f)

        config["email"]["app_password"] = body.password

        with open(CONFIG_PATH, "w") as f:
            yaml.safe_dump(config, f)

        return {
            "status": "success",
            "app_password": body.password
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
@router.get("/config/email/app_password")
def get_app_password():
    """
    Get the current app password for sending emails.
    """
    try:
        with open(CONFIG_PATH, "r") as f:
            config = yaml.safe_load(f)

        return {
            "app_password": config.get("email", {}).get("app_password", None)
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
@router.post("/config/email/sender")
def update_sender_email(body: SenderUpdate):
    """
    Update the sender email address for sending emails.

    Args:
        body (RecipientUpdate): JSON with the new sender email.

    Returns:
        dict: Success message.
    """
    try:
        with open(CONFIG_PATH, "r") as f:
            config = yaml.safe_load(f)

        config["email"]["sender"] = body.email

        with open(CONFIG_PATH, "w") as f:
            yaml.safe_dump(config, f)

        return {
            "status": "success",
            "sender": body.email
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
@router.get("/config/email/sender")
def get_sender_email():
    """
    Get the current sender email address for sending emails.
    """
    try:
        with open(CONFIG_PATH, "r") as f:
            config = yaml.safe_load(f)

        return {
            "sender": config.get("email", {}).get("sender", None)
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))