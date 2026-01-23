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
def create_img_from_bae64(image_base64, prefix="attachments") -> str:

    print("Creating image from base64 data...", type(image_base64))

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

    filename, buffer = create_img_from_bae64(image_base64, prefix=prefix)

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
        print(f"S3 upload failed [prefix={prefix}]: {e}")
        return None
