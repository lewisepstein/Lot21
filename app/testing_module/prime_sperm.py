import base64
import hashlib
import uuid
from cryptography.fernet import Fernet
from datetime import datetime, timedelta, timezone


from service_utils.db_utils.pg_db import PostgresDB

def derive_key_from_product_key(product_key: str) -> bytes:
    """
    Derive a Fernet-compatible key from product_key
    """
    sha = hashlib.sha256(product_key.encode()).digest()
    return base64.urlsafe_b64encode(sha)

def encrypt_payload(payload: str, product_key: str) -> str:
    key = derive_key_from_product_key(product_key)
    fernet = Fernet(key)
    return fernet.encrypt(payload.encode()).decode()

def decrypt_payload(token: str, product_key: str) -> str:
    key = derive_key_from_product_key(product_key)
    fernet = Fernet(key)
    return fernet.decrypt(token.encode()).decode()


def prime_sperm_auth(
    email: str = None,
    product_key: str = None,
    app_ssuid: str = None
) -> dict:

    if email is None or product_key is None or app_ssuid is None:
        return {
            "status": "failure",
            "message": "Missing required parameters."
        }
    else:
        email = email.strip()
        product_key = product_key.strip()
        app_ssuid = app_ssuid.strip()

        if email == "" or product_key == "" or app_ssuid == "":
            return {
                "status": "failure",
                "message": "Parameters cannot be empty."
            }
        
        if email == "admin@yopmail.com" and product_key == "2222222222222222":
            # Special admin case
            raw_token = f"{app_ssuid}:{uuid.uuid4()}:{datetime.now(timezone.utc).isoformat()}"
            encrypted_token = encrypt_payload(raw_token, product_key)
            return {
                "status": "success",
                "token": encrypted_token,
                "data": [
                    {
                        "email": email,
                        "app_ssuid": app_ssuid,
                        "app_registration_date": datetime.now(timezone.utc),
                        "expiry_date": datetime.now(timezone.utc) + timedelta(days=1),
                        "max_grace_period": 1,
                        "max_internet_period": 1,
                        "is_rental": True,
                        "created_on": datetime.now(timezone.utc)
                    }
                ]
            }
        else:
            return {
                "status": "failure",
                "message": "Invalid email or product key."
            }
