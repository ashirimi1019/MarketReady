import os
from urllib.parse import unquote, urlparse
from uuid import uuid4

import boto3
from botocore.exceptions import BotoCoreError, ClientError

from app.core.config import settings


def _s3_object_url(bucket: str, key: str, region: str | None) -> str:
    if not region or region == "us-east-1":
        return f"https://{bucket}.s3.amazonaws.com/{key}"
    return f"https://{bucket}.s3.{region}.amazonaws.com/{key}"


def s3_is_enabled() -> bool:
    return bool(settings.s3_bucket)


def _create_s3_client():
    kwargs: dict = {}
    if settings.s3_region:
        kwargs["region_name"] = settings.s3_region
    if settings.s3_endpoint_url:
        kwargs["endpoint_url"] = settings.s3_endpoint_url
    if settings.aws_access_key_id and settings.aws_secret_access_key:
        kwargs["aws_access_key_id"] = settings.aws_access_key_id
        kwargs["aws_secret_access_key"] = settings.aws_secret_access_key
        if settings.aws_session_token:
            kwargs["aws_session_token"] = settings.aws_session_token
    return boto3.client("s3", **kwargs)


def _object_key(prefix: str, user_id: str, filename: str) -> str:
    safe_name = os.path.basename(filename).replace(" ", "_")
    return f"{prefix.strip('/')}/{user_id}/{uuid4().hex}_{safe_name}"


def create_presigned_upload(
    user_id: str,
    filename: str,
    content_type: str,
    *,
    prefix: str = "proofs",
) -> dict:
    if not s3_is_enabled():
        raise ValueError("S3 bucket not configured")

    key = _object_key(prefix, user_id, filename)
    client = _create_s3_client()
    params = {
        "Bucket": settings.s3_bucket,
        "Key": key,
        "ContentType": content_type,
    }
    try:
        upload_url = client.generate_presigned_url(
            "put_object",
            Params=params,
            ExpiresIn=settings.s3_presign_expiry_seconds,
        )
    except (BotoCoreError, ClientError) as exc:
        raise RuntimeError(f"Unable to create S3 presigned upload URL: {exc}") from exc

    return {
        "upload_url": upload_url,
        "file_url": _s3_object_url(settings.s3_bucket, key, settings.s3_region),
        "key": key,
    }


def upload_bytes_to_s3(
    user_id: str,
    filename: str,
    content_type: str,
    content: bytes,
    *,
    prefix: str,
) -> dict:
    if not s3_is_enabled():
        raise ValueError("S3 bucket not configured")
    key = _object_key(prefix, user_id, filename)
    client = _create_s3_client()
    try:
        client.put_object(
            Bucket=settings.s3_bucket,
            Key=key,
            Body=content,
            ContentType=content_type or "application/octet-stream",
        )
    except (BotoCoreError, ClientError) as exc:
        raise RuntimeError(f"Unable to upload object to S3: {exc}") from exc
    return {
        "file_url": _s3_object_url(settings.s3_bucket, key, settings.s3_region),
        "key": key,
    }


def _extract_s3_key_from_url(url: str) -> str | None:
    if not url or not s3_is_enabled():
        return None

    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        return None

    bucket = (settings.s3_bucket or "").lower()
    host = (parsed.netloc or "").lower()
    path = unquote(parsed.path.lstrip("/"))

    if host.startswith(f"{bucket}.s3"):
        return path or None

    if host == "s3.amazonaws.com" or host.startswith("s3."):
        parts = path.split("/", 1)
        if len(parts) == 2 and parts[0] == settings.s3_bucket:
            return parts[1] or None

    return None


def is_s3_object_url(url: str) -> bool:
    return bool(_extract_s3_key_from_url(url))


def create_presigned_download_url(file_url: str, expires_in: int | None = None) -> str | None:
    if not s3_is_enabled():
        return None
    key = _extract_s3_key_from_url(file_url)
    if not key:
        return None
    client = _create_s3_client()
    expiry = expires_in or settings.s3_presign_expiry_seconds
    try:
        return client.generate_presigned_url(
            "get_object",
            Params={"Bucket": settings.s3_bucket, "Key": key},
            ExpiresIn=expiry,
        )
    except (BotoCoreError, ClientError):
        return None


def resolve_file_view_url(file_url: str) -> str:
    if not file_url:
        return file_url
    presigned = create_presigned_download_url(file_url)
    return presigned or file_url


def read_s3_object_bytes(file_url: str, max_bytes: int = 250_000) -> bytes | None:
    if not s3_is_enabled():
        return None
    key = _extract_s3_key_from_url(file_url)
    if not key:
        return None
    client = _create_s3_client()
    try:
        response = client.get_object(Bucket=settings.s3_bucket, Key=key)
        body = response["Body"]
        try:
            return body.read(max_bytes)
        finally:
            body.close()
    except (BotoCoreError, ClientError):
        return None


def storage_self_test() -> dict:
    base = {
        "s3_enabled": s3_is_enabled(),
        "bucket": settings.s3_bucket,
        "region": settings.s3_region,
    }
    if not s3_is_enabled():
        return {
            **base,
            "ok": False,
            "detail": "S3 bucket not configured.",
        }

    client = _create_s3_client()
    test_key = f"proofs/healthchecks/{uuid4().hex}.txt"
    results = {
        "get_bucket_location": False,
        "list_bucket": False,
        "put_object": False,
        "delete_object": False,
    }
    errors: dict[str, dict[str, str | None]] = {}

    try:
        client.get_bucket_location(Bucket=settings.s3_bucket)
        results["get_bucket_location"] = True
    except (BotoCoreError, ClientError) as exc:
        message = str(exc)
        error_code = None
        if isinstance(exc, ClientError):
            error_code = exc.response.get("Error", {}).get("Code")
            message = exc.response.get("Error", {}).get("Message") or message
        errors["get_bucket_location"] = {"error_code": error_code, "detail": message}

    try:
        client.list_objects_v2(Bucket=settings.s3_bucket, Prefix="proofs/", MaxKeys=1)
        results["list_bucket"] = True
    except (BotoCoreError, ClientError) as exc:
        message = str(exc)
        error_code = None
        if isinstance(exc, ClientError):
            error_code = exc.response.get("Error", {}).get("Code")
            message = exc.response.get("Error", {}).get("Message") or message
        errors["list_bucket"] = {"error_code": error_code, "detail": message}

    try:
        client.put_object(Bucket=settings.s3_bucket, Key=test_key, Body=b"ok")
        results["put_object"] = True
    except (BotoCoreError, ClientError) as exc:
        message = str(exc)
        error_code = None
        if isinstance(exc, ClientError):
            error_code = exc.response.get("Error", {}).get("Code")
            message = exc.response.get("Error", {}).get("Message") or message
        errors["put_object"] = {"error_code": error_code, "detail": message}

    try:
        client.delete_object(Bucket=settings.s3_bucket, Key=test_key)
        results["delete_object"] = True
    except (BotoCoreError, ClientError) as exc:
        message = str(exc)
        error_code = None
        if isinstance(exc, ClientError):
            error_code = exc.response.get("Error", {}).get("Code")
            message = exc.response.get("Error", {}).get("Message") or message
        errors["delete_object"] = {"error_code": error_code, "detail": message}

    ok = results["list_bucket"] and results["put_object"] and results["delete_object"]
    output = {
        **base,
        "ok": ok,
        "checks": results,
    }
    if errors:
        output["errors"] = errors
        if not ok:
            first_error = next(iter(errors.values()))
            output["error_code"] = first_error.get("error_code")
            output["detail"] = first_error.get("detail")
        else:
            output["detail"] = "Core access checks passed; some optional checks failed."
    elif ok:
        output["detail"] = "All storage checks passed."

    return output
