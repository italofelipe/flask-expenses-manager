from __future__ import annotations

from app.services.email_provider import (
    EmailMessage,
    ResendEmailProvider,
    StubEmailProvider,
    get_email_outbox,
)


def test_stub_email_provider_appends_to_outbox(app) -> None:
    with app.app_context():
        provider = StubEmailProvider()
        result = provider.send(
            EmailMessage(
                to_email="user@email.com",
                subject="Subject",
                html="<p>Hello</p>",
                text="Hello",
                tag="test_email",
            )
        )

        outbox = get_email_outbox()
        assert result.provider == "stub"
        assert len(outbox) == 1
        assert outbox[0]["email"] == "user@email.com"
        assert outbox[0]["tag"] == "test_email"


def test_resend_provider_posts_expected_payload(monkeypatch) -> None:
    monkeypatch.setenv("RESEND_API_KEY", "resend_test_key")
    monkeypatch.setenv("EMAIL_FROM", "Auraxis <noreply@auraxis.com.br>")
    provider = ResendEmailProvider()

    captured: dict[str, object] = {}

    class _Response:
        ok = True
        status_code = 200
        text = ""

        def json(self) -> dict[str, str]:
            return {"id": "email_123"}

    def _fake_post(url: str, *, json: object, timeout: float) -> _Response:
        captured["url"] = url
        captured["json"] = json
        captured["timeout"] = timeout
        return _Response()

    monkeypatch.setattr(provider._session, "post", _fake_post)

    result = provider.send(
        EmailMessage(
            to_email="user@email.com",
            subject="Subject",
            html="<p>Hello</p>",
            text="Hello",
            tag="account_confirmation",
        )
    )

    assert result.provider == "resend"
    assert result.provider_message_id == "email_123"
    assert str(captured["url"]).endswith("/emails")
