import boto3
import base64
import uuid
import io
from PIL import Image
import os
import re
from dotenv import load_dotenv

load_dotenv()

AWS_REGION = os.getenv("AWS_REGION")
AWS_S3_BUCKET = os.getenv("AWS_S3_BUCKET")
AWS_ACCESS_KEY = os.getenv("AWS_ACCESS_KEY")
AWS_SECRET_KEY = os.getenv("AWS_SECRET_KEY")

# Generated images and uploaded attachments are stored as plain S3 URLs. The
# bucket is private, so every URL handed to a browser or fetched server-side
# is signed first and expires; stored URLs stay unsigned and permanent.
SIGNED_URL_TTL_SEC = int(os.getenv("S3_SIGNED_URL_TTL_SEC", "21600"))  # 6 hours


def _s3_url_prefix() -> str:
    return f"https://{AWS_S3_BUCKET}.s3.{AWS_REGION}.amazonaws.com/"


def presign_s3_url(url, expires: int = SIGNED_URL_TTL_SEC):
    """Time-limited link for an object in our bucket; anything else is returned unchanged."""
    prefix = _s3_url_prefix()
    if not isinstance(url, str) or not url.startswith(prefix):
        return url
    key = url[len(prefix):].split("?", 1)[0]
    try:
        # Regional endpoint so the signed link keeps the same host as the stored URL
        client = boto3.client(
            "s3",
            region_name=AWS_REGION,
            endpoint_url=f"https://s3.{AWS_REGION}.amazonaws.com",
            aws_access_key_id=AWS_ACCESS_KEY,
            aws_secret_access_key=AWS_SECRET_KEY,
            config=boto3.session.Config(signature_version="s3v4", s3={"addressing_style": "virtual"}),
        )
        return client.generate_presigned_url(
            "get_object", Params={"Bucket": AWS_S3_BUCKET, "Key": key}, ExpiresIn=expires
        )
    except Exception:
        return url


def sign_ai_response(raw):
    """
    ai_response is stored as JSON {"text": ..., "images": [url, ...]} (a string
    in the database, a dict once parsed). Return the same shape with signed
    image links; plain text or unparseable values pass through untouched.
    """
    import json

    if isinstance(raw, dict):
        if raw.get("images"):
            raw = {**raw, "images": [presign_s3_url(u) for u in raw["images"]]}
        return raw
    if isinstance(raw, str) and raw.lstrip().startswith("{"):
        try:
            data = json.loads(raw)
        except (ValueError, TypeError):
            return raw
        if isinstance(data, dict) and data.get("images"):
            data["images"] = [presign_s3_url(u) for u in data["images"]]
            return json.dumps(data)
    return raw


# Validate base64 image data
# -----------------------------------------------------------
def validate_image_base64(image_base64: str) -> bool:
    # ---- Validate type ----
    if image_base64 is None:
        raise ValueError("image_base64 is None")

    if not isinstance(image_base64, str):
        raise TypeError(f"image_base64 must be str, got {type(image_base64)}")

    if not image_base64.strip():
        raise ValueError("image_base64 is empty")

    # ---- Strip data URL ----
    if image_base64.startswith("data:image"):
        image_base64 = image_base64.split(",", 1)[1]

    image_base64 = str(image_base64)

    # ---- Remove ALL whitespace/newlines ----
    try:
        image_base64 = re.sub(r"\s+", "", image_base64)
    except Exception as e:
        raise ValueError(f"Regex substitution failed. Type: {type(image_base64)}") from e

    # ---- Fix missing padding ----
    missing_padding = len(image_base64) % 4
    if missing_padding:
        image_base64 += "=" * (4 - missing_padding)

    # ---- Decode base64 ----
    try:
        image_bytes = base64.b64decode(image_base64, validate=True)
    except Exception as e:
        raise ValueError(f"Base64 decoding failed. Length: {len(image_base64)}") from e
    
    return image_bytes


# Connect to AWS S3
# -----------------------------------------------------------
def connect_s3():
    try:
        return boto3.client(
            "s3",
            region_name=AWS_REGION,
            aws_access_key_id=AWS_ACCESS_KEY,
            aws_secret_access_key=AWS_SECRET_KEY
        )
    except Exception as e:  
        raise Exception(f"Failed to connect to S3: {e}")


# Upload base64 image to S3 and return the S3 URL
# -----------------------------------------------------------
def create_img_from_base64(image_base64, prefix="attachments") -> str:


    image_bytes = validate_image_base64(image_base64)

    # ---- Load image ----
    try:
        image = Image.open(io.BytesIO(image_bytes))
        image.verify() 
        image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    except Exception as e:
        raise ValueError(f"Invalid image data (PIL failed): {type(e).__name__}: {e}") from e

    # ---- Save to buffer ----
    try:
        buffer = io.BytesIO()
        image.save(buffer, format="PNG")
        buffer.seek(0)
    except Exception as e:
        raise ValueError(f"Failed to save image: {type(e).__name__}: {e}") from e

    # ---- Generate filename ----
    try:
        filename = f"{prefix}/{uuid.uuid4().hex}.png"
    except Exception as e:
        raise ValueError(f"Failed to generate filename: {e}") from e

    return filename, buffer

def upload_base64_image_to_s3(image_base64, prefix="attachments") -> str:

    filename, buffer = create_img_from_base64(image_base64, prefix=prefix)

    # ---- Upload to S3 ----
    try:
        s3 = connect_s3()
        s3.upload_fileobj(
            buffer,
            AWS_S3_BUCKET,
            filename,
            ExtraArgs={
                "ContentType": "image/png",
            }
        )
        
        s3_url = f"https://{AWS_S3_BUCKET}.s3.{AWS_REGION}.amazonaws.com/{filename}"
        return s3_url
    except Exception as e:
        raise ValueError(f"S3 upload failed: {e}") from e


def safe_upload_image_to_s3(
    image_base64,
    prefix: str,
):
    try:
        return upload_base64_image_to_s3(
            image_base64=image_base64,
            prefix=prefix
        )
    except Exception as e:
        return None
