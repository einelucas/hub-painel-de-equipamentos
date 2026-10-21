"""Sanitização do HTML de e-mail e dos links usados nos modelos.

O editor avançado aceita HTML completo, então nada do conteúdo digitado é
confiável. A allowlist abaixo cobre apenas o necessário para um e-mail
transacional (tabelas, estilos inline e uma <style> para media queries) e
descarta scripts, formulários, iframes, handlers `on*` e URLs perigosas.
"""

from __future__ import annotations

import re
from html import escape
from html.parser import HTMLParser
from urllib.parse import urlsplit

ALLOWED_TAGS = frozenset({
    "a", "b", "blockquote", "body", "br", "center", "div", "em", "h1", "h2",
    "h3", "h4", "h5", "h6", "head", "hr", "html", "i", "img", "li", "meta",
    "ol", "p", "small", "span", "strong", "style", "table", "tbody", "td",
    "tfoot", "th", "thead", "title", "tr", "u", "ul",
})
VOID_TAGS = frozenset({"br", "hr", "img", "meta"})
# Tags cujo conteúdo (texto incluso) precisa desaparecer por completo.
DROP_CONTENT_TAGS = frozenset({
    "applet", "base", "embed", "form", "frame", "frameset", "iframe", "input",
    "link", "math", "noscript", "object", "script", "select", "svg", "template",
    "textarea",
})
ALLOWED_ATTRS = frozenset({
    "align", "alt", "bgcolor", "border", "cellpadding", "cellspacing", "charset",
    "class", "color", "colspan", "content", "dir", "face", "height", "href",
    "http-equiv", "lang", "name", "rel", "role", "rowspan", "size", "src",
    "style", "target", "title", "valign", "width",
})
_SAFE_SCHEMES = frozenset({"http", "https", "mailto", "tel"})
# Placeholders de URL são validados depois da substituição, no momento da
# renderização; preservá-los aqui evita perder href/src no salvamento.
_PLACEHOLDER_URL = re.compile(r"^\{[A-Za-z_][A-Za-z0-9_]*\}$")
_CSS_DANGER = re.compile(
    r"(?i)(expression\s*\(|javascript\s*:|vbscript\s*:|@import|behavior\s*:"
    r"|binding\s*:|-moz-binding|url\s*\(\s*['\"]?\s*(?:javascript|vbscript|data))"
)


def safe_url(value: str | None) -> str | None:
    """Aceita somente http(s), mailto e tel absolutos; nunca `javascript:`."""
    candidate = (value or "").strip()
    if not candidate or any(ord(char) < 32 for char in candidate):
        return None
    if candidate.startswith("//"):
        return None
    parsed = urlsplit(candidate)
    scheme = parsed.scheme.lower()
    if scheme not in _SAFE_SCHEMES:
        return None
    if scheme in {"http", "https"} and not parsed.netloc:
        return None
    return candidate


def _clean_css(value: str) -> str:
    return _CSS_DANGER.sub("", value)


class _EmailHtmlSanitizer(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.stack: list[str] = []
        self._drop_tag: str | None = None
        self._drop_depth = 0

    # --- tags ---------------------------------------------------------------
    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if self._drop_tag is not None:
            if tag == self._drop_tag:
                self._drop_depth += 1
            return
        if tag in DROP_CONTENT_TAGS:
            self._drop_tag = tag
            self._drop_depth = 1
            return
        if tag in VOID_TAGS:
            if tag in ALLOWED_TAGS:
                self.parts.append(self._render_tag(tag, attrs, closed=True))
            return
        if tag not in ALLOWED_TAGS:
            return
        self.stack.append(tag)
        self.parts.append(self._render_tag(tag, attrs))

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if self._drop_tag is not None or tag not in ALLOWED_TAGS:
            return
        self.parts.append(self._render_tag(tag, attrs, closed=tag in VOID_TAGS))

    def handle_endtag(self, tag: str) -> None:
        if self._drop_tag is not None:
            if tag == self._drop_tag:
                self._drop_depth -= 1
                if self._drop_depth <= 0:
                    self._drop_tag = None
                    self._drop_depth = 0
            return
        if tag not in self.stack:
            return
        while self.stack:
            current = self.stack.pop()
            self.parts.append(f"</{current}>")
            if current == tag:
                break

    # --- conteúdo -----------------------------------------------------------
    def handle_data(self, data: str) -> None:
        if self._drop_tag is not None:
            return
        if self.stack and self.stack[-1] == "style":
            self.parts.append(escape(_clean_css(data), quote=False))
            return
        self.parts.append(escape(data, quote=False))

    # --- atributos ----------------------------------------------------------
    def _render_tag(
        self, tag: str, attrs: list[tuple[str, str | None]], *, closed: bool = False
    ) -> str:
        rendered: list[str] = []
        has_blank_target = False
        for name, raw_value in attrs:
            attr = name.lower()
            if attr.startswith("on") or attr not in ALLOWED_ATTRS:
                continue
            value = raw_value or ""
            if attr in {"href", "src"}:
                if _PLACEHOLDER_URL.fullmatch(value.strip()):
                    value = value.strip()
                else:
                    cleaned_url = safe_url(value)
                    if cleaned_url is None:
                        continue
                    value = cleaned_url
            elif attr == "style":
                value = _clean_css(value)
            elif attr == "target":
                if value not in {"_blank", "_self"}:
                    continue
                has_blank_target = value == "_blank"
            elif attr == "http-equiv":
                if value.lower() != "content-type":
                    continue
            elif attr == "rel":
                continue
            rendered.append(f' {attr}="{escape(value, quote=True)}"')
        if has_blank_target:
            rendered.append(' rel="noopener noreferrer"')
        suffix = " /" if closed else ""
        return f"<{tag}{''.join(rendered)}{suffix}>"

    def close(self) -> None:  # encerra tags abertas por HTML malformado
        super().close()
        while self.stack:
            self.parts.append(f"</{self.stack.pop()}>")


def sanitize_email_html(value: str | None, *, max_length: int = 120_000) -> str:
    """Devolve HTML seguro; texto puro é escapado e vira conteúdo de bloco."""
    if not value:
        return ""
    source = value.replace("\x00", "")[:max_length]
    parser = _EmailHtmlSanitizer()
    parser.feed(source)
    parser.close()
    return "".join(parser.parts).strip()
