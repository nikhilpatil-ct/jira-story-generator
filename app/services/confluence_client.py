"""Confluence Cloud grounding: pull a page's body (and the text of any PDF attached to it) into the
same "app context" grounding block the drafter already uses, via the same Atlassian account/credentials
as the JIRA client (JIRA_EMAIL / JIRA_API_TOKEN)."""

import logging
import re
from html.parser import HTMLParser

import httpx

from app.config import settings
from app.services import file_parser

logger = logging.getLogger("confluence_client")

_BLOCK_TAGS = {"p", "div", "br", "li", "h1", "h2", "h3", "h4", "h5", "h6", "tr", "table"}


def _resolve_page_id(value: str) -> str:
    """CONFLUENCE_PAGE_ID is easy to mis-paste as a full page URL instead of the bare numeric id -
    accept either form."""
    value = value.strip()
    if value.isdigit():
        return value
    match = re.search(r"/pages/(\d+)", value) or re.search(r"[?&]pageId=(\d+)", value)
    return match.group(1) if match else value


class ConfluenceError(Exception):
    pass


class _TextExtractor(HTMLParser):
    """Minimal, dependency-free conversion of Confluence's storage-format (HTML-ish) body to plain text."""

    def __init__(self):
        super().__init__()
        self.chunks: list[str] = []

    def handle_starttag(self, tag, attrs):
        if tag in _BLOCK_TAGS:
            self.chunks.append("\n")

    def handle_endtag(self, tag):
        if tag in _BLOCK_TAGS:
            self.chunks.append("\n")

    def handle_data(self, data):
        if data.strip():
            self.chunks.append(data)


def _html_to_text(html: str) -> str:
    parser = _TextExtractor()
    parser.feed(html)
    lines = [ln.strip() for ln in "".join(parser.chunks).splitlines()]
    return "\n".join(ln for ln in lines if ln)


def _auth() -> tuple[str, str]:
    return (settings.jira_email, settings.jira_api_token)


async def _get(url: str, params: dict | None = None) -> dict:
    async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
        resp = await client.get(url, params=params, auth=_auth(), headers={"Accept": "application/json"})
    if resp.status_code >= 300:
        raise ConfluenceError(f"Confluence API error {resp.status_code}: {resp.text}")
    return resp.json()


async def get_page(page_id: str) -> dict:
    """Raw page content (storage-format body + metadata) for one Confluence page."""
    page_id = _resolve_page_id(page_id)
    url = f"{settings.confluence_base_url.rstrip('/')}/wiki/rest/api/content/{page_id}"
    return await _get(url, params={"expand": "body.storage"})


async def get_page_text(page_id: str) -> str:
    page = await get_page(page_id)
    storage_html = page.get("body", {}).get("storage", {}).get("value", "")
    return _html_to_text(storage_html)


async def get_page_meta(page_id: str | None = None) -> dict | None:
    """{"page_id", "title", "url"} for the configured Confluence page, or None if it isn't configured or
    can't be reached — used to attach a reference link on a created JIRA issue."""
    page_id = page_id or settings.confluence_page_id
    if not settings.confluence_base_url or not page_id:
        return None
    try:
        page = await get_page(page_id)
    except (ConfluenceError, httpx.HTTPError) as exc:
        logger.warning("Could not fetch Confluence page metadata for %s: %s", page_id, exc)
        return None

    title = page.get("title") or f"Confluence page {page_id}"
    base = page.get("_links", {}).get("base") or f"{settings.confluence_base_url.rstrip('/')}/wiki"
    webui = page.get("_links", {}).get("webui", "")
    url = f"{base}{webui}" if webui else f"{settings.confluence_base_url.rstrip('/')}/wiki/pages/viewpage.action?pageId={page_id}"
    return {"page_id": page_id, "title": title, "url": url}


async def get_pdf_attachments_with_content(page_id: str | None = None) -> list[dict]:
    """[{filename, content: bytes}] for every PDF attached to the configured page — the raw bytes, ready
    to be re-attached to a JIRA issue as a reference document."""
    page_id = page_id or settings.confluence_page_id
    if not settings.confluence_base_url or not page_id:
        return []
    try:
        attachments = await list_pdf_attachments(page_id)
    except (ConfluenceError, httpx.HTTPError) as exc:
        logger.warning("Could not list attachments for Confluence page %s: %s", page_id, exc)
        return []

    out: list[dict] = []
    for att in attachments:
        try:
            content = await _download(att["download_url"])
            out.append({"filename": att["filename"], "content": content})
        except Exception as exc:  # noqa: BLE001 - one bad attachment must not block the others
            logger.warning("Could not download attachment %s: %s", att["filename"], exc)
    return out


async def list_pdf_attachments(page_id: str) -> list[dict]:
    """[{filename, download_url}] for every PDF attached to the page (empty if none)."""
    page_id = _resolve_page_id(page_id)
    url = f"{settings.confluence_base_url.rstrip('/')}/wiki/rest/api/content/{page_id}/child/attachment"
    data = await _get(url, params={"expand": "metadata"})
    base = data.get("_links", {}).get("base") or f"{settings.confluence_base_url.rstrip('/')}/wiki"
    attachments = []
    for item in data.get("results", []):
        media_type = item.get("metadata", {}).get("mediaType", "")
        title = item.get("title", "")
        if media_type == "application/pdf" or title.lower().endswith(".pdf"):
            download = item.get("_links", {}).get("download", "")
            attachments.append({"filename": title, "download_url": base + download})
    return attachments


async def _download(url: str) -> bytes:
    # Confluence's attachment download endpoint 302s to a signed content URL - must follow it.
    async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
        resp = await client.get(url, auth=_auth())
    if resp.status_code >= 300:
        raise ConfluenceError(f"Confluence attachment download failed {resp.status_code}: {resp.text}")
    return resp.content


async def get_page_context(page_id: str | None = None) -> str:
    """Grounding text for the drafter: the Confluence page body, plus the extracted text of any PDF
    attached to that page. Returns "" (never raises) when Confluence isn't configured or the fetch
    fails — this is bonus grounding, never a hard dependency of the generation pipeline."""
    page_id = page_id or settings.confluence_page_id
    if not settings.confluence_configured and not (settings.confluence_base_url and page_id):
        return ""

    blocks: list[str] = []
    try:
        page_text = await get_page_text(page_id)
        if page_text:
            blocks.append(f"# Confluence page context\n\n{page_text}")
    except (ConfluenceError, httpx.HTTPError) as exc:
        logger.warning("Could not fetch Confluence page %s: %s", page_id, exc)
        return ""

    try:
        pdf_attachments = await list_pdf_attachments(page_id)
    except (ConfluenceError, httpx.HTTPError) as exc:
        logger.warning("Could not list attachments for Confluence page %s: %s", page_id, exc)
        pdf_attachments = []

    for att in pdf_attachments:
        try:
            content = await _download(att["download_url"])
            pdf_text = file_parser.extract_text(att["filename"], content)
            if pdf_text:
                blocks.append(f"# PDF attachment: {att['filename']}\n\n{pdf_text}")
        except Exception as exc:  # noqa: BLE001 - one bad attachment must not block the others or the page text
            logger.warning("Could not extract text from attachment %s: %s", att["filename"], exc)

    return "\n\n---\n\n".join(blocks)
