"""App knowledge base: detect which known applications a transcript refers to and load their context.

The knowledge/ directory holds one Markdown file per application (business flow, use cases, design, and
tech stack), each with a small frontmatter block. On startup we parse those files into a DB mapping
(app name/aliases -> file). During the pipeline we scan the transcript against that mapping and inject
the matched app's knowledge into the drafting prompt, so generated items are grounded in what the app
actually does rather than only what a single meeting mentioned.
"""

import re
from pathlib import Path

from app.services import db

KNOWLEDGE_DIR = Path(__file__).resolve().parent.parent.parent / "knowledge"
_PROJECT_ROOT = KNOWLEDGE_DIR.parent

# Ignore aliases shorter than this to avoid noisy false-positive matches (e.g. "FX", "GL").
_MIN_ALIAS_LEN = 3


def _parse_frontmatter(text: str) -> tuple[dict, str]:
    """Split a leading `---` frontmatter block from the markdown body.

    Minimal, dependency-free parser for the simple `key: value` (+ `aliases: [a, b]`) format we author.
    Returns (metadata, body).
    """
    if not text.startswith("---"):
        return {}, text.strip()
    parts = text.split("---", 2)
    if len(parts) < 3:
        return {}, text.strip()
    meta_block, body = parts[1], parts[2]
    meta: dict = {}
    for line in meta_block.splitlines():
        line = line.strip()
        if not line or ":" not in line:
            continue
        key, _, value = line.partition(":")
        key, value = key.strip().lower(), value.strip()
        if key == "aliases":
            value = value.strip().lstrip("[").rstrip("]")
            meta[key] = [a.strip() for a in value.split(",") if a.strip()]
        else:
            meta[key] = value
    return meta, body.strip()


def load_from_disk() -> list[dict]:
    """Parse every knowledge/*.md file into a catalog entry (key, name, aliases, description, file_path)."""
    entries: list[dict] = []
    if not KNOWLEDGE_DIR.exists():
        return entries
    for path in sorted(KNOWLEDGE_DIR.glob("*.md")):
        meta, _ = _parse_frontmatter(path.read_text(encoding="utf-8"))
        key = meta.get("key") or path.stem
        name = meta.get("name") or key
        aliases = list(meta.get("aliases") or [])
        if name not in aliases:  # the display name is always matchable
            aliases = [name, *aliases]
        entries.append(
            {
                "key": key,
                "name": name,
                "aliases": aliases,
                "description": meta.get("description", ""),
                "file_path": path.resolve().relative_to(_PROJECT_ROOT).as_posix(),
            }
        )
    return entries


def seed_catalog() -> int:
    """Sync the DB app_catalog mapping from the knowledge/ directory. Returns the number of apps registered."""
    entries = load_from_disk()
    db.sync_app_catalog(entries)
    return len(entries)


def list_catalog() -> list[dict]:
    """Return the DB app_catalog mapping (name/aliases -> knowledge file), name-sorted."""
    return db.all_apps()


def _alias_pattern(alias: str) -> re.Pattern:
    """Case-insensitive match of `alias` as a whole token (spaces/hyphens inside the alias are allowed)."""
    return re.compile(rf"(?<![\w]){re.escape(alias)}(?![\w])", re.IGNORECASE)


def detect_apps(text: str, catalog: list[dict] | None = None) -> list[dict]:
    """Return catalog entries whose name or any alias appears in `text`, in catalog order, deduped by app."""
    if not text:
        return []
    catalog = catalog if catalog is not None else db.all_apps()
    matched: list[dict] = []
    for app in catalog:
        for alias in app["aliases"]:
            if len(alias) < _MIN_ALIAS_LEN:
                continue
            if _alias_pattern(alias).search(text):
                matched.append(app)
                break
    return matched


def _load_body(file_path: str) -> str:
    path = _PROJECT_ROOT / file_path
    if not path.exists():
        return ""
    _, body = _parse_frontmatter(path.read_text(encoding="utf-8"))
    return body


def build_context(apps: list[dict]) -> str:
    """Concatenate the knowledge body of each matched app into a single grounding block for the drafter."""
    blocks = [body for app in apps if (body := _load_body(app["file_path"]))]
    return "\n\n---\n\n".join(blocks)
