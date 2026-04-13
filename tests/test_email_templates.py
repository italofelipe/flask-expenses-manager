"""Tests for Auraxis branded email templates.

Covers:
- HTML structure: doctype, viewport, brand colours, fonts
- CTA link is present and uses the provided URL
- Plain-text fallback contains the URL
- Password reset template follows the same contract
"""

from __future__ import annotations

from app.services.email_templates import (
    render_confirmation_email,
    render_due_soon_email,
    render_password_reset_email,
)

CONFIRM_URL = "https://app.auraxis.com.br/auth/confirm-email?token=abc123"
RESET_URL = "https://app.auraxis.com.br/auth/reset-password?token=xyz456"


class TestRenderConfirmationEmail:
    def test_returns_html_and_text_tuple(self) -> None:
        result = render_confirmation_email(confirmation_url=CONFIRM_URL)
        assert isinstance(result, tuple)
        assert len(result) == 2

    def test_html_is_valid_doctype(self) -> None:
        html, _ = render_confirmation_email(confirmation_url=CONFIRM_URL)
        assert html.strip().startswith("<!DOCTYPE html>")

    def test_html_contains_confirmation_url(self) -> None:
        html, _ = render_confirmation_email(confirmation_url=CONFIRM_URL)
        assert CONFIRM_URL in html

    def test_html_contains_brand_colour(self) -> None:
        html, _ = render_confirmation_email(confirmation_url=CONFIRM_URL)
        # Primary brand amber
        assert "#ffab1a" in html

    def test_html_contains_brand_name(self) -> None:
        html, _ = render_confirmation_email(confirmation_url=CONFIRM_URL)
        assert "Auraxis" in html

    def test_html_contains_heading_font(self) -> None:
        html, _ = render_confirmation_email(confirmation_url=CONFIRM_URL)
        assert "Playfair Display" in html

    def test_html_contains_body_font(self) -> None:
        html, _ = render_confirmation_email(confirmation_url=CONFIRM_URL)
        assert "Raleway" in html

    def test_html_contains_cta_button(self) -> None:
        html, _ = render_confirmation_email(confirmation_url=CONFIRM_URL)
        assert "Confirmar email" in html

    def test_html_contains_expiry_notice(self) -> None:
        html, _ = render_confirmation_email(confirmation_url=CONFIRM_URL)
        assert "24 horas" in html

    def test_html_has_preview_text(self) -> None:
        html, _ = render_confirmation_email(confirmation_url=CONFIRM_URL)
        assert "Confirme seu email" in html

    def test_text_contains_url(self) -> None:
        _, text = render_confirmation_email(confirmation_url=CONFIRM_URL)
        assert CONFIRM_URL in text

    def test_text_is_plain_string(self) -> None:
        _, text = render_confirmation_email(confirmation_url=CONFIRM_URL)
        assert "<" not in text


class TestRenderPasswordResetEmail:
    def test_returns_html_and_text_tuple(self) -> None:
        result = render_password_reset_email(reset_url=RESET_URL)
        assert isinstance(result, tuple)
        assert len(result) == 2

    def test_html_contains_reset_url(self) -> None:
        html, _ = render_password_reset_email(reset_url=RESET_URL)
        assert RESET_URL in html

    def test_html_contains_cta_button(self) -> None:
        html, _ = render_password_reset_email(reset_url=RESET_URL)
        assert "Redefinir senha" in html

    def test_html_contains_expiry_notice(self) -> None:
        html, _ = render_password_reset_email(reset_url=RESET_URL)
        assert "1 hora" in html

    def test_text_contains_url(self) -> None:
        _, text = render_password_reset_email(reset_url=RESET_URL)
        assert RESET_URL in text

    def test_text_is_plain_string(self) -> None:
        _, text = render_password_reset_email(reset_url=RESET_URL)
        assert "<" not in text

    def test_html_contains_brand_colour(self) -> None:
        html, _ = render_password_reset_email(reset_url=RESET_URL)
        assert "#ffab1a" in html


class TestRenderDueSoonEmail:
    def test_returns_html_and_text_tuple(self) -> None:
        result = render_due_soon_email(
            title="Aluguel", amount_formatted="1500.00", days_before_due=7
        )
        assert isinstance(result, tuple)
        assert len(result) == 2

    def test_html_is_valid_doctype(self) -> None:
        html, _ = render_due_soon_email(
            title="Aluguel", amount_formatted="1500.00", days_before_due=7
        )
        assert html.strip().startswith("<!DOCTYPE html>")

    def test_html_contains_brand_colour(self) -> None:
        html, _ = render_due_soon_email(
            title="Aluguel", amount_formatted="1500.00", days_before_due=7
        )
        assert "#ffab1a" in html

    def test_html_contains_brand_name(self) -> None:
        html, _ = render_due_soon_email(
            title="Aluguel", amount_formatted="1500.00", days_before_due=7
        )
        assert "Auraxis" in html

    def test_html_contains_cta_button(self) -> None:
        html, _ = render_due_soon_email(
            title="Aluguel", amount_formatted="1500.00", days_before_due=7
        )
        assert "Ver no Auraxis" in html

    def test_d7_html_contains_title_and_amount(self) -> None:
        html, _ = render_due_soon_email(
            title="Aluguel", amount_formatted="1500.00", days_before_due=7
        )
        assert "Aluguel" in html
        assert "1500.00" in html
        assert "Pendência vencendo em breve" in html

    def test_d1_html_heading_is_tomorrow(self) -> None:
        html, _ = render_due_soon_email(
            title="Aluguel", amount_formatted="750.00", days_before_due=1
        )
        assert "Amanhã vence uma pendência" in html
        assert "amanhã" in html

    def test_d1_html_contains_title_and_amount(self) -> None:
        html, _ = render_due_soon_email(
            title="Cartão Nubank", amount_formatted="320.50", days_before_due=1
        )
        assert "Cartão Nubank" in html
        assert "320.50" in html

    def test_text_is_plain_string(self) -> None:
        _, text = render_due_soon_email(
            title="Aluguel", amount_formatted="1500.00", days_before_due=7
        )
        assert "<" not in text

    def test_text_contains_app_url(self) -> None:
        _, text = render_due_soon_email(
            title="Aluguel", amount_formatted="1500.00", days_before_due=7
        )
        assert "app.auraxis.com.br" in text

    def test_d7_text_mentions_days(self) -> None:
        _, text = render_due_soon_email(
            title="Aluguel", amount_formatted="1500.00", days_before_due=7
        )
        assert "7 dias" in text

    def test_d1_text_mentions_amanha(self) -> None:
        _, text = render_due_soon_email(
            title="Aluguel", amount_formatted="1500.00", days_before_due=1
        )
        assert "amanhã" in text
