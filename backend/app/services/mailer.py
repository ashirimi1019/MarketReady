from __future__ import annotations

from dataclasses import dataclass
import smtplib
from email.message import EmailMessage

import boto3
import httpx

from app.core.config import settings


@dataclass
class MailSendResult:
    provider: str
    provider_message_id: str | None = None


def _provider_order() -> list[str]:
    raw = (settings.mail_provider_order or "").strip()
    candidates = raw.split(",") if raw else ["smtp", "resend", "ses"]
    order: list[str] = []
    for candidate in candidates:
        provider = candidate.strip().lower()
        if provider in {"smtp", "resend", "ses"} and provider not in order:
            order.append(provider)
    return order or ["smtp", "resend", "ses"]


def _smtp_is_configured() -> bool:
    return bool(settings.smtp_host and settings.smtp_port)


def _resend_is_configured() -> bool:
    return bool(settings.resend_api_key and settings.resend_api_base)


def _ses_is_configured() -> bool:
    region = settings.ses_region or settings.s3_region
    return bool(region)


def mail_is_configured() -> bool:
    if not settings.mail_enabled or not settings.mail_from:
        return False
    for provider in _provider_order():
        if provider == "smtp" and _smtp_is_configured():
            return True
        if provider == "resend" and _resend_is_configured():
            return True
        if provider == "ses" and _ses_is_configured():
            return True
    return False


def _build_client() -> smtplib.SMTP:
    host = settings.smtp_host or ""
    port = int(settings.smtp_port)
    timeout = int(settings.smtp_timeout_seconds)
    if settings.smtp_use_ssl:
        return smtplib.SMTP_SSL(host=host, port=port, timeout=timeout)
    return smtplib.SMTP(host=host, port=port, timeout=timeout)


def _build_smtp_message(
    *,
    to_email: str,
    subject: str,
    text_body: str,
    html_body: str | None,
) -> EmailMessage:
    message = EmailMessage()
    message["From"] = settings.mail_from
    message["To"] = to_email
    message["Subject"] = subject
    message.set_content(text_body)
    if html_body:
        message.add_alternative(html_body, subtype="html")
    return message


def _send_via_smtp(message: EmailMessage) -> MailSendResult:
    if not _smtp_is_configured():
        raise RuntimeError("SMTP is not configured")
    with _build_client() as client:
        if settings.smtp_use_tls and not settings.smtp_use_ssl:
            client.ehlo()
            client.starttls()
            client.ehlo()

        if settings.smtp_username:
            client.login(settings.smtp_username, settings.smtp_password or "")
        client.send_message(message)
    return MailSendResult(provider="smtp")


def _send_via_resend(
    *,
    to_email: str,
    subject: str,
    text_body: str,
    html_body: str | None,
) -> MailSendResult:
    if not _resend_is_configured():
        raise RuntimeError("Resend is not configured")
    payload: dict = {
        "from": settings.mail_from,
        "to": [to_email],
        "subject": subject,
        "text": text_body,
    }
    if html_body:
        payload["html"] = html_body
    headers = {
        "Authorization": f"Bearer {settings.resend_api_key}",
        "Content-Type": "application/json",
    }
    url = f"{settings.resend_api_base.rstrip('/')}/emails"
    timeout = float(settings.smtp_timeout_seconds)
    with httpx.Client(timeout=timeout) as client:
        response = client.post(url, headers=headers, json=payload)
    if response.status_code >= 400:
        body = response.text[:300]
        raise RuntimeError(f"Resend request failed ({response.status_code}): {body}")
    data = response.json() if response.text else {}
    return MailSendResult(provider="resend", provider_message_id=str(data.get("id") or ""))


def _send_via_ses(
    *,
    to_email: str,
    subject: str,
    text_body: str,
    html_body: str | None,
) -> MailSendResult:
    if not _ses_is_configured():
        raise RuntimeError("SES is not configured")
    ses_region = settings.ses_region or settings.s3_region or "us-east-1"
    client_kwargs: dict = {"region_name": ses_region}
    if settings.ses_access_key_id and settings.ses_secret_access_key:
        client_kwargs["aws_access_key_id"] = settings.ses_access_key_id
        client_kwargs["aws_secret_access_key"] = settings.ses_secret_access_key
        if settings.ses_session_token:
            client_kwargs["aws_session_token"] = settings.ses_session_token
    client = boto3.client("ses", **client_kwargs)
    body = {"Text": {"Data": text_body, "Charset": "UTF-8"}}
    if html_body:
        body["Html"] = {"Data": html_body, "Charset": "UTF-8"}
    send_args = {
        "Source": settings.mail_from,
        "Destination": {"ToAddresses": [to_email]},
        "Message": {
            "Subject": {"Data": subject, "Charset": "UTF-8"},
            "Body": body,
        },
    }
    if settings.ses_configuration_set:
        send_args["ConfigurationSetName"] = settings.ses_configuration_set
    response = client.send_email(**send_args)
    return MailSendResult(
        provider="ses",
        provider_message_id=str(response.get("MessageId") or ""),
    )


def send_email(
    *,
    to_email: str,
    subject: str,
    text_body: str,
    html_body: str | None = None,
) -> MailSendResult:
    if not settings.mail_enabled:
        raise RuntimeError("Email delivery is disabled")
    if not settings.mail_from:
        raise RuntimeError("MAIL_FROM is not configured")

    message = _build_smtp_message(
        to_email=to_email,
        subject=subject,
        text_body=text_body,
        html_body=html_body,
    )
    errors: list[str] = []
    attempted = 0
    for provider in _provider_order():
        try:
            if provider == "smtp":
                if not _smtp_is_configured():
                    continue
                attempted += 1
                return _send_via_smtp(message)
            if provider == "resend":
                if not _resend_is_configured():
                    continue
                attempted += 1
                return _send_via_resend(
                    to_email=to_email,
                    subject=subject,
                    text_body=text_body,
                    html_body=html_body,
                )
            if provider == "ses":
                if not _ses_is_configured():
                    continue
                attempted += 1
                return _send_via_ses(
                    to_email=to_email,
                    subject=subject,
                    text_body=text_body,
                    html_body=html_body,
                )
        except Exception as exc:
            errors.append(f"{provider}: {exc}")

    if attempted == 0:
        raise RuntimeError("No email provider is configured (smtp/resend/ses)")
    raise RuntimeError("All configured email providers failed: " + " | ".join(errors[:3]))


def send_verification_code_email(
    *,
    to_email: str,
    username: str,
    code: str,
    ttl_minutes: int,
) -> MailSendResult:
    subject = "Verify your Market Pathways account"
    text = (
        f"Hi {username},\n\n"
        f"Your verification code is: {code}\n\n"
        f"This code expires in about {ttl_minutes} minutes.\n"
        "If you did not request this, you can ignore this email.\n"
    )
    html = (
        f"<p>Hi {username},</p>"
        f"<p>Your verification code is: <strong>{code}</strong></p>"
        f"<p>This code expires in about {ttl_minutes} minutes.</p>"
        "<p>If you did not request this, you can ignore this email.</p>"
    )
    return send_email(to_email=to_email, subject=subject, text_body=text, html_body=html)


def send_password_reset_email(
    *,
    to_email: str,
    username: str,
    code: str,
    ttl_minutes: int,
) -> MailSendResult:
    subject = "Reset your Market Pathways password"
    text = (
        f"Hi {username},\n\n"
        f"Your password reset code is: {code}\n\n"
        f"This code expires in about {ttl_minutes} minutes.\n"
        "If you did not request this, please ignore this email.\n"
    )
    html = (
        f"<p>Hi {username},</p>"
        f"<p>Your password reset code is: <strong>{code}</strong></p>"
        f"<p>This code expires in about {ttl_minutes} minutes.</p>"
        "<p>If you did not request this, please ignore this email.</p>"
    )
    return send_email(to_email=to_email, subject=subject, text_body=text, html_body=html)
