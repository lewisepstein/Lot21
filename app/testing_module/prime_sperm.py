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

    db = PostgresDB()

    record = db.read(
        'test_auth',
        conditions={
            'email': email,
            'product_key': product_key
        }
    )

    if not record:
        return {
            "status": "failure",
            "message": "Invalid Product Key for the email address."
        }

    product_key = record[0]["product_key"]

    try:
        data = db.update(
            'test_auth',
            {
                'email': email,
                'product_key': product_key,
                'customer_app_ssuid': app_ssuid,
                'app_registration_date': datetime.now(timezone.utc),
                'expiry_date': datetime.now(timezone.utc) + timedelta(days=1),
            },
            conditions={
                'id': record[0]['id']
            }
        ) 

        if not data:
            return {
                "status": "failure",
                "message": "Failed to log authentication attempt."
            }
        
        # Convert SQLAlchemy Row objects to dictionaries
        data = [dict(row._mapping) for row in data] if data else []
        
    except Exception as e:
        return {
            "status": "failure",
            "message": f"Database error: {str(e)}"
        }
    
    # Combine app_ssuid + uuid
    raw_token = f"{app_ssuid}:{uuid.uuid4()}:{datetime.now(timezone.utc).isoformat()}"

    encrypted_token = encrypt_payload(raw_token, product_key)

    return {
        "status": "success",
        "token": encrypted_token,
        "data": data
    }
