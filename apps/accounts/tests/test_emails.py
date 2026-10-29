import pytest
from django.core import mail
from django.core.management import call_command
from django.urls import reverse

from apps.accounts.tasks import EMAIL_COPY, send_otp
from apps.core.testing import PASSWORD

EMAIL_PURPOSES = ["verify_email", "login", "reset_password", "verify_phone"]


def html_of(message):
    (html, mimetype), = message.alternatives
    assert mimetype == "text/html"
    return html


@pytest.mark.parametrize("purpose", EMAIL_PURPOSES)
def test_otp_email_has_text_and_html_versions(purpose, settings):
    settings.DEFAULT_FROM_EMAIL = "Learnify <no-reply@learnify.test>"
    settings.SUPPORT_EMAIL = "help@learnify.test"
    send_otp("email", "ada@example.com", "482913", purpose)

    assert len(mail.outbox) == 1
    msg = mail.outbox[0]
    assert msg.to == ["ada@example.com"]
    assert msg.from_email == "Learnify <no-reply@learnify.test>"
    assert msg.subject == EMAIL_COPY[purpose]["subject"]

    html = html_of(msg)
    for body in (msg.body, html):
        assert "482913" in body
        assert "expires in" in body and "10 minutes" in body
        assert EMAIL_COPY[purpose]["heading"] in body
        assert "help@learnify.test" in body
        # nothing left unrendered
        assert "{{" not in body and "{%" not in body
    assert html.lstrip().startswith("<!DOCTYPE html>")
    assert "<" not in msg.body


def test_text_version_is_not_html_escaped(settings):
    settings.SUPPORT_EMAIL = "help+otp@learnify.test"
    send_otp("email", "ada@example.com", "482913", "login")
    msg = mail.outbox[0]
    assert "Learnify staff will never ask you for it." in msg.body
    assert "&#x27;" not in msg.body and "&amp;" not in msg.body
    assert "didn't request" in msg.body


def test_sms_otp_does_not_send_email(settings):
    settings.DEBUG = True
    send_otp("sms", "+2348031112222", "482913", "verify_phone")
    assert mail.outbox == []


@pytest.mark.django_db
def test_register_sends_verification_email_end_to_end(api_client,
                                                      django_capture_on_commit_callbacks):
    with django_capture_on_commit_callbacks(execute=True):
        res = api_client.post(reverse("auth-register"), {
            "email": "tolu@example.com", "phone": "0803 111 2222",
            "first_name": "Tolu", "last_name": "Ade", "password": PASSWORD,
        }, format="json")
    assert res.status_code == 201, res.data

    assert len(mail.outbox) == 1
    msg = mail.outbox[0]
    assert msg.to == ["tolu@example.com"]
    assert msg.subject == "Verify your Learnify email"
    code = next(line.strip() for line in msg.body.splitlines()
                if line.strip().isdigit())

    # the code in the email actually verifies the account
    ok = api_client.post(reverse("auth-otp-verify"), {
        "identifier": "tolu@example.com", "purpose": "verify_email", "code": code,
    }, format="json")
    assert ok.status_code == 200, ok.data
    assert ok.data["user"]["is_email_verified"] is True


def test_send_test_email_command(capsys):
    call_command("send_test_email", "ops@example.com", "--purpose", "reset_password")
    assert len(mail.outbox) == 1
    assert mail.outbox[0].subject == "[Test] Reset your Learnify password"
    assert "123456" in mail.outbox[0].body
    assert "Sent test email to ops@example.com" in capsys.readouterr().out
