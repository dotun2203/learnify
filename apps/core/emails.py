"""Templated email. Every email has a plain-text and an HTML version.

Templates live in templates/emails/<name>.txt and templates/emails/<name>.html
and both extend the shared layouts in templates/emails/base.*.
"""
from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils import timezone


def base_context():
    return {
        "brand_name": "Learnify",
        "frontend_url": settings.FRONTEND_URL,
        "support_email": settings.SUPPORT_EMAIL,
        "year": timezone.now().year,
    }


def render_email(name, context):
    """Return (text_body, html_body) for templates/emails/<name>.*"""
    ctx = {**base_context(), **context}
    text = render_to_string(f"emails/{name}.txt", ctx).strip() + "\n"
    html = render_to_string(f"emails/{name}.html", ctx)
    return text, html


def send_templated_email(*, to, subject, template, context=None):
    """Send one email to one or more addresses. Raises on SMTP failure so the
    calling Celery task can retry."""
    recipients = [to] if isinstance(to, str) else list(to)
    text, html = render_email(template, {"subject": subject, **(context or {})})
    message = EmailMultiAlternatives(
        subject=subject, body=text,
        from_email=settings.DEFAULT_FROM_EMAIL, to=recipients,
    )
    message.attach_alternative(html, "text/html")
    message.send()
