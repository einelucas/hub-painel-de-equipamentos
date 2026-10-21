"""Modelos HTML: variáveis, sanitização, layout e proteção do sandbox."""

from __future__ import annotations

from dataclasses import replace

import pytest

from app.core.errors import DomainError
from app.modules.notifications.html_sanitizer import safe_url, sanitize_email_html
from app.modules.notifications.template_renderer import (
    ALLOWED_FIELDS,
    EmailContext,
    default_content,
    render_email,
    render_string,
    sample_context,
    validate_content,
    validate_custom_html,
    validate_template,
)
from app.modules.notifications.template_service import sample_required


def _context(**overrides: object) -> EmailContext:
    base = sample_context("KICKOFF", "https://hub.example.test")
    values = dict(base.values)
    present = set(base.present)
    for key, value in overrides.items():
        values[key] = str(value)
        if value in ("", None):
            present.discard(key)
        else:
            present.add(key)
    return replace(base, values=values, present=frozenset(present), url=values["url_equipamento"])


def test_default_template_has_hub_identity_and_action_button() -> None:
    rendered = render_email(default_content("KICKOFF"), _context())

    assert rendered.subject == "Kickoff: Bomba centrífuga de exemplo"
    assert "Hub de Automação" in rendered.html
    assert "Planejamento" in rendered.html
    assert "Painel de Equipamentos" in rendered.html
    assert "TAG-EXEMPLO-001" in rendered.html
    assert 'href="https://hub.example.test/equipamentos"' in rendered.html
    assert "@media only screen and (max-width:620px)" in rendered.html
    assert "<script" not in rendered.html.lower()
    assert "Abrir equipamento no Hub" in rendered.html


def test_optional_fields_are_hidden_when_absent() -> None:
    context = _context(tag="", fornecedor="", url_equipamento="")
    rendered = render_email(default_content("KICKOFF"), context)

    assert "TAG" not in rendered.html
    assert "Fornecedor" not in rendered.html
    assert "Abrir equipamento no Hub" not in rendered.html


def test_dynamic_values_are_escaped_in_html() -> None:
    context = _context(equipamento="<script>alert(1)</script>")
    rendered = render_email(default_content("KICKOFF"), context)

    assert "<script>alert(1)</script>" not in rendered.html
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in rendered.html


def test_text_alternative_lists_details_and_link() -> None:
    rendered = render_email(default_content("DELIVERY_REMINDER"), _context())

    assert "<" not in rendered.text
    assert "Equipamento: Bomba centrífuga de exemplo" in rendered.text
    assert "Prazo de entrega:" in rendered.text
    assert "https://hub.example.test/equipamentos" in rendered.text


def test_custom_html_is_sanitized_and_keeps_variables() -> None:
    custom = (
        '<div onclick="steal()"><script>alert(1)</script>'
        '<a href="javascript:alert(1)">x</a>'
        "<p>{equipamento}</p></div>"
    )
    content = replace(
        default_content("FUP"),
        use_custom_html=True,
        custom_html=custom,
    )
    rendered = render_email(content, _context())

    assert "<script" not in rendered.html.lower()
    assert "onclick" not in rendered.html
    assert "javascript:" not in rendered.html
    assert "Bomba centrífuga de exemplo" in rendered.html


def test_custom_html_with_css_braces_is_valid() -> None:
    validate_custom_html(
        "<style>@media (max-width:620px){.a{width:100%}}</style><p>{equipamento}</p>"
    )
    with pytest.raises(DomainError, match="não permitida"):
        validate_custom_html("<p>{senha}</p>")


def test_placeholders_only_allow_known_fields() -> None:
    validate_template("{equipamento} — {tag} — {url_equipamento}")
    assert "dias_restantes" in ALLOWED_FIELDS
    for invalid in ("{unknown}", "{equipamento.__class__}", "{equipamento:>20}", "Mensagem {"):
        with pytest.raises(DomainError):
            validate_template(invalid)


def test_advanced_mode_requires_html() -> None:
    content = replace(default_content("KICKOFF"), use_custom_html=True, custom_html="  ")
    with pytest.raises(DomainError, match="HTML"):
        validate_content(content)


def test_render_string_escapes_quotes_in_html_mode() -> None:
    values = {"equipamento": 'Bomba "A" & Cia'}

    assert render_string("{equipamento}", values, as_html=True) == (
        "Bomba &quot;A&quot; &amp; Cia"
    )
    assert render_string("{equipamento}", values) == 'Bomba "A" & Cia'


def test_sanitizer_strips_dangerous_markup_and_urls() -> None:
    cleaned = sanitize_email_html(
        '<p onmouseover="x()">ok</p>'
        '<img src="data:image/png;base64,AAAA" onerror="x()" />'
        '<a href="//evil.example">rel</a>'
        '<a href="https://ok.example/path">ok</a>'
        "<iframe src=\"https://evil.example\"></iframe>"
    )

    assert "onmouseover" not in cleaned
    assert "onerror" not in cleaned
    assert "data:image" not in cleaned
    assert "evil.example" not in cleaned
    assert "iframe" not in cleaned
    assert 'href="https://ok.example/path"' in cleaned
    assert safe_url("javascript:alert(1)") is None
    assert safe_url("mailto:qa@example.test") == "mailto:qa@example.test"


def test_sample_data_never_contains_real_identifiers() -> None:
    context = sample_context("STARTUP_REMINDER", "http://localhost:3000")

    assert "exemplo" in context.values["equipamento"].lower()
    assert "@" not in context.values["responsavel"]
    assert context.values["url_equipamento"].startswith("http://localhost:3000/")


def test_blank_subject_falls_back_to_rendered_title() -> None:
    content = replace(default_content("KICKOFF"), subject="   ", title="{equipamento}")
    rendered = render_email(content, _context())

    assert rendered.subject == "Bomba centrífuga de exemplo"


def test_custom_html_placeholder_url_survives_sanitization() -> None:
    custom = '<a href="{url_equipamento}">Abrir</a><img src="{tag}" alt="TAG" />'
    cleaned = sanitize_email_html(custom)

    assert 'href="{url_equipamento}"' in cleaned
    assert 'src="{tag}"' in cleaned

    content = replace(
        default_content("KICKOFF"), use_custom_html=True, custom_html=custom
    )
    rendered = render_email(content, _context())
    assert 'href="https://hub.example.test/equipamentos"' in rendered.html


def test_subject_and_meta_survive_safely() -> None:
    rendered = render_email(
        default_content("KICKOFF"), _context(equipamento="Bomba\nBcc: outro@example.test")
    )
    assert "\n" not in rendered.subject
    assert rendered.subject == "Kickoff: Bomba Bcc: outro@example.test"

    cleaned = sanitize_email_html(
        '<meta http-equiv="Content-Type" content="text/html; charset=UTF-8" />'
        '<meta http-equiv="refresh" content="0;url=https://evil.example" />'
    )
    assert 'http-equiv="Content-Type"' in cleaned
    assert "refresh" not in cleaned


def test_sandbox_always_requires_fictitious_data() -> None:
    assert sample_required(False, "sandbox") is True
    assert sample_required(True, "live") is True
    assert sample_required(False, "live") is False
    assert sample_required(False, "log") is False
