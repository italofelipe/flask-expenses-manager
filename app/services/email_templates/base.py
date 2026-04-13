"""Auraxis transactional email template system.

All emails are rendered from a shared base layout that enforces brand
consistency: dark background, amber/gold brand colour, Playfair Display
headings, Raleway body — matching the web application's design tokens.

Usage::

    from app.services.email_templates.base import render_confirmation_email

    html, text = render_confirmation_email(confirmation_url="https://...")
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Brand tokens (mirrored from auraxis-web design system)
# ---------------------------------------------------------------------------

_COLOR_BG_BASE = "#0b0909"
_COLOR_BG_SURFACE = "#272020"
_COLOR_BG_ELEVATED = "#413939"
_COLOR_BRAND = "#ffab1a"
_COLOR_BRAND_HOVER = "#ffbe4d"
_COLOR_BRAND_DARK = "#f59600"
_COLOR_TEXT_PRIMARY = "#faf9f9"
_COLOR_TEXT_SECONDARY = "#d1c7c7"
_COLOR_TEXT_MUTED = "#9b8888"
_COLOR_BORDER = "rgba(65, 57, 57, 0.8)"

_FONT_HEADING = "'Playfair Display', 'Georgia', 'Times New Roman', serif"
_FONT_BODY = "'Raleway', 'Segoe UI', 'Helvetica Neue', Arial, sans-serif"

_LOGO_URL = "https://app.auraxis.com.br/logo.png"
_APP_URL = "https://app.auraxis.com.br"


# ---------------------------------------------------------------------------
# Base layout
# ---------------------------------------------------------------------------


def _base_layout(*, title: str, preview_text: str, body_html: str) -> str:
    """Wrap email body in the Auraxis branded shell.

    The layout is intentionally table-based for maximum email-client
    compatibility (Gmail, Outlook, Apple Mail, mobile).
    """
    return f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <meta http-equiv="X-UA-Compatible" content="IE=edge" />
  <title>{title}</title>
  <!--[if mso]>
  <noscript>
    <xml><o:OfficeDocumentSettings><o:PixelsPerInch>96</o:PixelsPerInch></o:OfficeDocumentSettings></xml>
  </noscript>
  <![endif]-->
  <style>
    @import url('https://fonts.googleapis.com/css2?family=Playfair+Display:wght@600;700&family=Raleway:wght@400;500;600&display=swap');
    body, table, td, a {{ -webkit-text-size-adjust: 100%; -ms-text-size-adjust: 100%; }}
    table, td {{ mso-table-lspace: 0pt; mso-table-rspace: 0pt; }}
    img {{ -ms-interpolation-mode: bicubic; border: 0; height: auto; line-height: 100%; outline: none; text-decoration: none; }}
    body {{ margin: 0; padding: 0; background-color: {_COLOR_BG_BASE}; }}
    .email-wrapper {{ background-color: {_COLOR_BG_BASE}; width: 100%; }}
    .email-container {{ max-width: 600px; margin: 0 auto; }}
    .btn {{ display: inline-block; background-color: {_COLOR_BRAND}; color: {_COLOR_BG_BASE} !important; font-family: {_FONT_BODY}; font-size: 15px; font-weight: 600; text-decoration: none; padding: 14px 32px; border-radius: 8px; mso-padding-alt: 0; }}
    .btn-wrapper {{ padding: 8px 0; }}
    @media only screen and (max-width: 600px) {{
      .email-container {{ width: 100% !important; }}
      .email-body {{ padding: 24px 20px !important; }}
    }}
  </style>
</head>
<body>
  <!-- Preview text (hidden) -->
  <div style="display:none;font-size:1px;line-height:1px;max-height:0;max-width:0;opacity:0;overflow:hidden;mso-hide:all;">{preview_text}&nbsp;&zwnj;&nbsp;&zwnj;&nbsp;&zwnj;&nbsp;&zwnj;</div>

  <table role="presentation" class="email-wrapper" cellpadding="0" cellspacing="0" border="0" width="100%">
    <tr>
      <td align="center" style="padding: 32px 16px;">

        <!-- Container -->
        <table role="presentation" class="email-container" cellpadding="0" cellspacing="0" border="0" width="600">

          <!-- Header / Logo -->
          <tr>
            <td align="center" style="padding: 32px 0 24px;">
              <a href="{_APP_URL}" style="text-decoration: none;">
                <span style="font-family: {_FONT_HEADING}; font-size: 28px; font-weight: 700; color: {_COLOR_BRAND}; letter-spacing: -0.5px;">Auraxis</span>
              </a>
            </td>
          </tr>

          <!-- Card body -->
          <tr>
            <td class="email-body" style="background-color: {_COLOR_BG_SURFACE}; border-radius: 16px; border: 1px solid {_COLOR_BG_ELEVATED}; padding: 40px 48px;">
              {body_html}
            </td>
          </tr>

          <!-- Footer -->
          <tr>
            <td align="center" style="padding: 28px 0 0;">
              <p style="font-family: {_FONT_BODY}; font-size: 12px; color: {_COLOR_TEXT_MUTED}; margin: 0 0 8px;">
                Este é um email automático — por favor não responda.
              </p>
              <p style="font-family: {_FONT_BODY}; font-size: 12px; color: {_COLOR_TEXT_MUTED}; margin: 0;">
                &copy; 2026 Auraxis &bull;
                <a href="{_APP_URL}" style="color: {_COLOR_TEXT_MUTED}; text-decoration: underline;">app.auraxis.com.br</a>
              </p>
            </td>
          </tr>

        </table>
        <!-- /Container -->

      </td>
    </tr>
  </table>
</body>
</html>"""


# ---------------------------------------------------------------------------
# Email templates
# ---------------------------------------------------------------------------


def render_confirmation_email(*, confirmation_url: str) -> tuple[str, str]:
    """Render the account confirmation email.

    Returns:
        (html, text) tuple ready to pass to EmailMessage.
    """
    body_html = f"""
      <!-- Heading -->
      <h1 style="font-family: {_FONT_HEADING}; font-size: 26px; font-weight: 700;
                 color: {_COLOR_TEXT_PRIMARY}; margin: 0 0 8px; line-height: 1.2;">
        Confirme sua conta
      </h1>
      <p style="font-family: {_FONT_BODY}; font-size: 13px; font-weight: 600;
                color: {_COLOR_BRAND}; margin: 0 0 24px; text-transform: uppercase;
                letter-spacing: 1px;">
        Auraxis &mdash; Finanças pessoais
      </p>

      <!-- Divider -->
      <div style="border-top: 1px solid {_COLOR_BG_ELEVATED}; margin: 0 0 28px;"></div>

      <!-- Body -->
      <p style="font-family: {_FONT_BODY}; font-size: 15px; color: {_COLOR_TEXT_SECONDARY};
                line-height: 1.65; margin: 0 0 16px;">
        Olá! Você está a um passo de ter controle total das suas finanças.
        Clique no botão abaixo para confirmar seu endereço de email e ativar sua conta.
      </p>

      <!-- CTA -->
      <table role="presentation" cellpadding="0" cellspacing="0" border="0" style="margin: 32px 0;">
        <tr>
          <td class="btn-wrapper" align="left"
              style="border-radius: 8px; background-color: {_COLOR_BRAND};">
            <!--[if mso]>
            <v:roundrect xmlns:v="urn:schemas-microsoft-com:vml" xmlns:w="urn:schemas-microsoft-com:office:word"
              href="{confirmation_url}" style="height:48px;v-text-anchor:middle;width:220px;" arcsize="17%"
              strokecolor="{_COLOR_BRAND_DARK}" fillcolor="{_COLOR_BRAND}">
              <w:anchorlock/>
              <center style="color:{_COLOR_BG_BASE};font-family:{_FONT_BODY};font-size:15px;font-weight:600;">
                Confirmar email
              </center>
            </v:roundrect>
            <![endif]-->
            <!--[if !mso]><!-->
            <a href="{confirmation_url}" class="btn"
               style="background-color: {_COLOR_BRAND}; color: {_COLOR_BG_BASE};
                      font-family: {_FONT_BODY}; font-size: 15px; font-weight: 600;
                      text-decoration: none; display: inline-block;
                      padding: 14px 32px; border-radius: 8px;">
              Confirmar email
            </a>
            <!--<![endif]-->
          </td>
        </tr>
      </table>

      <!-- Expiry notice -->
      <p style="font-family: {_FONT_BODY}; font-size: 13px; color: {_COLOR_TEXT_MUTED};
                line-height: 1.6; margin: 0 0 24px;">
        Este link expira em <strong style="color: {_COLOR_TEXT_SECONDARY};">24 horas</strong>.
        Se você não criou uma conta na Auraxis, pode ignorar este email com segurança.
      </p>

      <!-- Divider -->
      <div style="border-top: 1px solid {_COLOR_BG_ELEVATED}; margin: 0 0 20px;"></div>

      <!-- Fallback URL -->
      <p style="font-family: {_FONT_BODY}; font-size: 12px; color: {_COLOR_TEXT_MUTED};
                line-height: 1.6; margin: 0;">
        Se o botão não funcionar, copie e cole este link no seu navegador:<br/>
        <a href="{confirmation_url}"
           style="color: {_COLOR_BRAND}; word-break: break-all; font-size: 12px;">
          {confirmation_url}
        </a>
      </p>
    """

    html = _base_layout(
        title="Confirme sua conta Auraxis",
        preview_text="Confirme seu email para ativar sua conta Auraxis.",
        body_html=body_html,
    )

    text = (
        "Confirme sua conta Auraxis\n"
        "==========================\n\n"
        "Olá! Você está a um passo de ter controle total das suas finanças.\n\n"
        "Clique no link abaixo para confirmar seu email e ativar sua conta:\n\n"
        f"{confirmation_url}\n\n"
        "Este link expira em 24 horas.\n\n"
        "Se você não criou uma conta na Auraxis, ignore este email.\n\n"
        "— Equipe Auraxis\n"
        "https://app.auraxis.com.br\n"
    )

    return html, text


def render_password_reset_email(*, reset_url: str) -> tuple[str, str]:
    """Render the password reset email."""
    body_html = f"""
      <h1 style="font-family: {_FONT_HEADING}; font-size: 26px; font-weight: 700;
                 color: {_COLOR_TEXT_PRIMARY}; margin: 0 0 8px; line-height: 1.2;">
        Redefinir senha
      </h1>
      <p style="font-family: {_FONT_BODY}; font-size: 13px; font-weight: 600;
                color: {_COLOR_BRAND}; margin: 0 0 24px; text-transform: uppercase;
                letter-spacing: 1px;">
        Auraxis &mdash; Finanças pessoais
      </p>

      <div style="border-top: 1px solid {_COLOR_BG_ELEVATED}; margin: 0 0 28px;"></div>

      <p style="font-family: {_FONT_BODY}; font-size: 15px; color: {_COLOR_TEXT_SECONDARY};
                line-height: 1.65; margin: 0 0 16px;">
        Recebemos uma solicitação para redefinir a senha da sua conta.
        Clique no botão abaixo para criar uma nova senha.
      </p>

      <table role="presentation" cellpadding="0" cellspacing="0" border="0" style="margin: 32px 0;">
        <tr>
          <td align="left" style="border-radius: 8px; background-color: {_COLOR_BRAND};">
            <a href="{reset_url}" class="btn"
               style="background-color: {_COLOR_BRAND}; color: {_COLOR_BG_BASE};
                      font-family: {_FONT_BODY}; font-size: 15px; font-weight: 600;
                      text-decoration: none; display: inline-block;
                      padding: 14px 32px; border-radius: 8px;">
              Redefinir senha
            </a>
          </td>
        </tr>
      </table>

      <p style="font-family: {_FONT_BODY}; font-size: 13px; color: {_COLOR_TEXT_MUTED};
                line-height: 1.6; margin: 0 0 24px;">
        Este link expira em <strong style="color: {_COLOR_TEXT_SECONDARY};">1 hora</strong>.
        Se você não solicitou a redefinição de senha, ignore este email — sua conta está segura.
      </p>

      <div style="border-top: 1px solid {_COLOR_BG_ELEVATED}; margin: 0 0 20px;"></div>

      <p style="font-family: {_FONT_BODY}; font-size: 12px; color: {_COLOR_TEXT_MUTED};
                line-height: 1.6; margin: 0;">
        Se o botão não funcionar, copie e cole este link no seu navegador:<br/>
        <a href="{reset_url}"
           style="color: {_COLOR_BRAND}; word-break: break-all; font-size: 12px;">
          {reset_url}
        </a>
      </p>
    """

    html = _base_layout(
        title="Redefinir senha — Auraxis",
        preview_text="Solicitação de redefinição de senha para sua conta Auraxis.",
        body_html=body_html,
    )

    text = (
        "Redefinir senha — Auraxis\n"
        "=========================\n\n"
        "Recebemos uma solicitação para redefinir a senha da sua conta.\n\n"
        "Acesse o link abaixo para criar uma nova senha:\n\n"
        f"{reset_url}\n\n"
        "Este link expira em 1 hora.\n\n"
        "Se você não solicitou a redefinição, ignore este email.\n\n"
        "— Equipe Auraxis\n"
        "https://app.auraxis.com.br\n"
    )

    return html, text


def render_account_deletion_email() -> tuple[str, str]:
    """Render the LGPD account deletion confirmation email.

    Returns:
        (html, text) tuple ready to pass to EmailMessage.
    """
    body_html = f"""
      <h1 style="font-family: {_FONT_HEADING}; font-size: 26px; font-weight: 700;
                 color: {_COLOR_TEXT_PRIMARY}; margin: 0 0 8px; line-height: 1.2;">
        Sua conta foi excluída
      </h1>
      <p style="font-family: {_FONT_BODY}; font-size: 13px; font-weight: 600;
                color: {_COLOR_BRAND}; margin: 0 0 24px; text-transform: uppercase;
                letter-spacing: 1px;">
        Auraxis &mdash; Finanças pessoais
      </p>

      <div style="border-top: 1px solid {_COLOR_BG_ELEVATED}; margin: 0 0 28px;"></div>

      <p style="font-family: {_FONT_BODY}; font-size: 15px; color: {_COLOR_TEXT_SECONDARY};
                line-height: 1.65; margin: 0 0 16px;">
        Confirmamos que sua conta Auraxis foi excluída com sucesso.
        Todos os seus dados pessoais foram anonimizados em conformidade com a
        <strong style="color: {_COLOR_TEXT_PRIMARY};">Lei Geral de Proteção de Dados (LGPD)</strong>.
      </p>

      <p style="font-family: {_FONT_BODY}; font-size: 15px; color: {_COLOR_TEXT_SECONDARY};
                line-height: 1.65; margin: 0 0 24px;">
        Se você não solicitou a exclusão da sua conta ou acredita que isso ocorreu
        por engano, entre em contato com nossa equipe de suporte imediatamente.
      </p>

      <div style="border-top: 1px solid {_COLOR_BG_ELEVATED}; margin: 0 0 20px;"></div>

      <p style="font-family: {_FONT_BODY}; font-size: 13px; color: {_COLOR_TEXT_MUTED};
                line-height: 1.6; margin: 0;">
        Obrigado por ter utilizado a Auraxis. Esperamos ter contribuído positivamente
        para o seu gerenciamento financeiro.
      </p>
    """

    html = _base_layout(
        title="Conta excluída — Auraxis",
        preview_text="Sua conta Auraxis foi excluída com sucesso (LGPD).",
        body_html=body_html,
    )

    text = (
        "Conta excluída — Auraxis\n"
        "========================\n\n"
        "Confirmamos que sua conta Auraxis foi excluída com sucesso.\n\n"
        "Todos os seus dados pessoais foram anonimizados em conformidade com a\n"
        "Lei Geral de Proteção de Dados (LGPD).\n\n"
        "Se você não solicitou a exclusão da sua conta ou acredita que isso ocorreu\n"
        "por engano, entre em contato com nossa equipe de suporte imediatamente.\n\n"
        "Obrigado por ter utilizado a Auraxis.\n\n"
        "— Equipe Auraxis\n"
        "https://app.auraxis.com.br\n"
    )

    return html, text


def render_due_soon_email(
    *,
    title: str,
    amount_formatted: str,
    days_before_due: int,
) -> tuple[str, str]:
    """Render the transaction due-soon reminder email (D-7 or D-1).

    Args:
        title: Transaction title (e.g., "Aluguel").
        amount_formatted: Pre-formatted amount string (e.g., "1500.00").
        days_before_due: 7 or 1.

    Returns:
        (html, text) tuple ready to pass to EmailMessage.
    """
    if days_before_due == 1:
        email_title = "Amanhã vence uma pendência"
        preview = f"Amanhã vence R$ {amount_formatted} — {title}."
        heading = "Amanhã vence uma pendência"
        intro = (
            f'Sua transação <strong style="color: {_COLOR_TEXT_PRIMARY};">{title}</strong> '
            f'vence <strong style="color: {_COLOR_BRAND};">amanhã</strong> no valor de '
            f'<strong style="color: {_COLOR_TEXT_PRIMARY};">R$ {amount_formatted}</strong>.'
        )
    else:
        email_title = "Pendência vencendo em breve"
        preview = f"Você tem R$ {amount_formatted} vencendo em {days_before_due} dias — {title}."
        heading = "Pendência vencendo em breve"
        intro = (
            f'Sua transação <strong style="color: {_COLOR_TEXT_PRIMARY};">{title}</strong> '
            f'vence em <strong style="color: {_COLOR_BRAND};">{days_before_due} dias</strong> '
            f'no valor de <strong style="color: {_COLOR_TEXT_PRIMARY};">R$ {amount_formatted}</strong>.'
        )

    body_html = f"""
      <h1 style="font-family: {_FONT_HEADING}; font-size: 26px; font-weight: 700;
                 color: {_COLOR_TEXT_PRIMARY}; margin: 0 0 8px; line-height: 1.2;">
        {heading}
      </h1>
      <p style="font-family: {_FONT_BODY}; font-size: 13px; font-weight: 600;
                color: {_COLOR_BRAND}; margin: 0 0 24px; text-transform: uppercase;
                letter-spacing: 1px;">
        Auraxis &mdash; Finanças pessoais
      </p>

      <div style="border-top: 1px solid {_COLOR_BG_ELEVATED}; margin: 0 0 28px;"></div>

      <p style="font-family: {_FONT_BODY}; font-size: 15px; color: {_COLOR_TEXT_SECONDARY};
                line-height: 1.65; margin: 0 0 24px;">
        {intro}
      </p>

      <!-- CTA -->
      <table role="presentation" cellpadding="0" cellspacing="0" border="0" style="margin: 8px 0 32px;">
        <tr>
          <td align="left" style="border-radius: 8px; background-color: {_COLOR_BRAND};">
            <!--[if mso]>
            <v:roundrect xmlns:v="urn:schemas-microsoft-com:vml" xmlns:w="urn:schemas-microsoft-com:office:word"
              href="{_APP_URL}" style="height:48px;v-text-anchor:middle;width:200px;" arcsize="17%"
              strokecolor="{_COLOR_BRAND_DARK}" fillcolor="{_COLOR_BRAND}">
              <w:anchorlock/>
              <center style="color:{_COLOR_BG_BASE};font-family:{_FONT_BODY};font-size:15px;font-weight:600;">
                Ver no Auraxis
              </center>
            </v:roundrect>
            <![endif]-->
            <!--[if !mso]><!-->
            <a href="{_APP_URL}"
               style="background-color: {_COLOR_BRAND}; color: {_COLOR_BG_BASE};
                      font-family: {_FONT_BODY}; font-size: 15px; font-weight: 600;
                      text-decoration: none; display: inline-block;
                      padding: 14px 32px; border-radius: 8px;">
              Ver no Auraxis
            </a>
            <!--<![endif]-->
          </td>
        </tr>
      </table>

      <div style="border-top: 1px solid {_COLOR_BG_ELEVATED}; margin: 0 0 20px;"></div>

      <p style="font-family: {_FONT_BODY}; font-size: 12px; color: {_COLOR_TEXT_MUTED};
                line-height: 1.6; margin: 0;">
        Para gerenciar suas preferências de notificação, acesse as configurações no aplicativo.
      </p>
    """

    html = _base_layout(
        title=email_title,
        preview_text=preview,
        body_html=body_html,
    )

    if days_before_due == 1:
        text = (
            f"Amanhã vence uma pendência — Auraxis\n"
            f"=====================================\n\n"
            f"Sua transação '{title}' vence amanhã no valor de R$ {amount_formatted}.\n\n"
            f"Acesse o Auraxis para gerenciar suas finanças:\n"
            f"{_APP_URL}\n\n"
            f"Para gerenciar preferências de notificação, acesse as configurações no app.\n\n"
            f"— Equipe Auraxis\n"
        )
    else:
        text = (
            f"Pendência vencendo em breve — Auraxis\n"
            f"======================================\n\n"
            f"Sua transação '{title}' vence em {days_before_due} dias "
            f"no valor de R$ {amount_formatted}.\n\n"
            f"Acesse o Auraxis para gerenciar suas finanças:\n"
            f"{_APP_URL}\n\n"
            f"Para gerenciar preferências de notificação, acesse as configurações no app.\n\n"
            f"— Equipe Auraxis\n"
        )

    return html, text


__all__ = [
    "render_account_deletion_email",
    "render_confirmation_email",
    "render_due_soon_email",
    "render_password_reset_email",
]
