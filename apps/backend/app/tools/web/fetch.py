from __future__ import annotations

import ipaddress
import socket
from html import unescape
from typing import Literal
from urllib.parse import urlsplit

import httpx
from bs4 import BeautifulSoup

ExtractMode = Literal["markdown", "text"]
_BLOCK_TAGS = ("h1", "h2", "h3", "h4", "p", "li", "pre", "blockquote")


def validate_public_web_url(url: str) -> str:
    parsed = urlsplit(url.strip())
    if parsed.scheme not in {"http", "https"}:
        msg = "Only http and https URLs are allowed."
        raise ValueError(msg)
    if not parsed.hostname:
        msg = "URL must include a hostname."
        raise ValueError(msg)
    if parsed.username or parsed.password:
        msg = "URLs with embedded credentials are not allowed."
        raise ValueError(msg)

    try:
        addrinfo = socket.getaddrinfo(parsed.hostname, parsed.port or 80, type=socket.SOCK_STREAM)
    except OSError as exc:
        msg = f"URL must resolve to a public host. Resolution failed for `{parsed.hostname}`."
        raise ValueError(msg) from exc

    for _, _, _, _, sockaddr in addrinfo:
        host = sockaddr[0]
        address = ipaddress.ip_address(host)
        if (
            address.is_private
            or address.is_loopback
            or address.is_link_local
            or address.is_multicast
            or address.is_reserved
            or address.is_unspecified
        ):
            msg = "URL must resolve to a public host."
            raise ValueError(msg)

    return parsed.geturl()


def extract_readable_content(
    *,
    html: str,
    url: str,
    extract_mode: ExtractMode,
    max_chars: int,
) -> dict[str, object]:
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "noscript", "iframe", "svg"]):
        tag.decompose()

    title = _resolve_title(soup, url)
    root = soup.find("main") or soup.find("article") or soup.body or soup
    body_blocks = _collect_blocks(root)

    if extract_mode == "markdown":
        lines: list[str] = [f"# {title}", ""]
        lines.extend(body_blocks)
        content = _normalize_newlines("\n\n".join(lines))
    else:
        content = _normalize_newlines("\n\n".join(body_blocks)) or title

    content, truncated = _truncate_text(content, max_chars)
    return {
        "url": url,
        "title": title,
        "extract_mode": extract_mode,
        "content": content,
        "truncated": truncated,
    }


def fetch_web_document(
    *,
    url: str,
    extract_mode: ExtractMode,
    max_chars: int,
    timeout_seconds: float,
    max_response_bytes: int,
) -> dict[str, object]:
    safe_url = validate_public_web_url(url)
    headers = {"User-Agent": "Nanobot Agent Console/0.2.0"}

    with httpx.Client(
        timeout=timeout_seconds,
        follow_redirects=True,
        max_redirects=3,
        headers=headers,
    ) as client:
        with client.stream("GET", safe_url) as response:
            response.raise_for_status()
            content_type = (response.headers.get("content-type") or "").lower()
            payload_bytes = _read_limited_bytes(response, max_response_bytes)
            final_url = str(response.url)

    text = payload_bytes.decode("utf-8", errors="ignore")
    if "text/html" in content_type or "<html" in text.lower():
        payload = extract_readable_content(
            html=text,
            url=final_url,
            extract_mode=extract_mode,
            max_chars=max_chars,
        )
    elif "text/plain" in content_type:
        content, truncated = _truncate_text(_normalize_newlines(text), max_chars)
        payload = {
            "url": url,
            "title": urlsplit(final_url).hostname or final_url,
            "extract_mode": extract_mode,
            "content": content,
            "truncated": truncated,
        }
    else:
        msg = "Unsupported content type for web_fetch."
        raise ValueError(msg)

    payload["final_url"] = final_url
    return payload


def _collect_blocks(root: BeautifulSoup) -> list[str]:
    blocks: list[str] = []
    seen: set[str] = set()
    for tag in root.find_all(_BLOCK_TAGS):
        text = _normalize_inline_text(tag.get_text("\n", strip=True))
        if not text or text in seen:
            continue
        seen.add(text)
        if tag.name == "pre":
            blocks.append(f"```\n{text}\n```")
            continue
        if tag.name == "li":
            blocks.append(f"- {text}")
            continue
        if tag.name and tag.name.startswith("h") and len(tag.name) == 2:
            try:
                heading_level = min(max(int(tag.name[1]), 1), 4)
            except ValueError:
                heading_level = 2
            blocks.append(f"{'#' * heading_level} {text}")
            continue
        if tag.name == "blockquote":
            blocks.append(f"> {text}")
            continue
        blocks.append(text)

    if blocks:
        return blocks

    fallback = _normalize_inline_text(root.get_text("\n", strip=True))
    return [fallback] if fallback else []


def _normalize_inline_text(value: str) -> str:
    text = unescape(value or "")
    normalized = [segment.strip() for segment in text.splitlines() if segment.strip()]
    return "\n".join(normalized)


def _normalize_newlines(value: str) -> str:
    chunks = [chunk.rstrip() for chunk in value.splitlines()]
    cleaned: list[str] = []
    previous_blank = False
    for chunk in chunks:
        if not chunk.strip():
            if previous_blank:
                continue
            previous_blank = True
            cleaned.append("")
            continue
        previous_blank = False
        cleaned.append(chunk)
    return "\n".join(cleaned).strip()


def _truncate_text(value: str, max_chars: int) -> tuple[str, bool]:
    clamped = max(1, max_chars)
    if len(value) <= clamped:
        return value, False
    return value[:clamped], True


def _resolve_title(soup: BeautifulSoup, url: str) -> str:
    if soup.title and soup.title.string:
        title = soup.title.string.strip()
        if title:
            return title
    heading = soup.find(["h1", "h2"])
    if heading:
        title = heading.get_text(" ", strip=True)
        if title:
            return title
    return urlsplit(url).hostname or url


def _read_limited_bytes(response: httpx.Response, max_response_bytes: int) -> bytes:
    chunks: list[bytes] = []
    total = 0
    for chunk in response.iter_bytes():
        total += len(chunk)
        if total > max_response_bytes:
            msg = "Response body exceeded the configured safety limit."
            raise ValueError(msg)
        chunks.append(chunk)
    return b"".join(chunks)
