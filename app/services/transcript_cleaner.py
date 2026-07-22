import re

_TIMESTAMP_RE = re.compile(
    r"\[?\(?\b\d{1,2}:\d{2}(?::\d{2})?\b\)?\]?|\[\d{1,2}:\d{2}\s*(?:AM|PM)?\]", re.IGNORECASE
)
_SPEAKER_LABEL_RE = re.compile(r"^\s*\[?([A-Z][\w .'-]{0,30})\]?\s*:\s*", re.MULTILINE)
_FILLER_WORDS_RE = re.compile(
    r"\b(um+|uh+|erm+|hmm+|like,?|you know,?|i mean,?|sort of|kind of|basically|actually|"
    r"okay okay|so so|right\?)\b",
    re.IGNORECASE,
)
_LAUGH_NOISE_RE = re.compile(r"\[(laughs?|laughter|inaudible|crosstalk|silence|pause)\]", re.IGNORECASE)
_WORD_REPEAT_RE = re.compile(r"\b(\w+)([ ,]+\1\b)+", re.IGNORECASE)
_WHITESPACE_RE = re.compile(r"[ \t]{2,}")
_BLANK_LINES_RE = re.compile(r"\n{3,}")


def looks_like_transcript(text: str) -> bool:
    """Heuristic: does this read like a spoken meeting transcript (timestamps / "Name:" speaker
    turns) rather than a structured document (BRD, PRD, spec)? Structured documents skip the
    speech-cleanup passes below, since filler-word/speaker-label stripping is tuned for spoken
    dialogue and would otherwise clip legitimate prose (e.g. "actually" inside a requirement)."""
    lines = [line for line in text.split("\n") if line.strip()]
    if not lines:
        return False
    signal_lines = sum(1 for line in lines if _TIMESTAMP_RE.search(line) or _SPEAKER_LABEL_RE.match(line))
    return signal_lines / len(lines) > 0.15


def _dedupe_sentences(text: str) -> str:
    seen: set[str] = set()
    out_lines = []
    for line in text.split("\n"):
        key = re.sub(r"\s+", " ", line).strip().lower()
        if key and key in seen:
            continue
        if key:
            seen.add(key)
        out_lines.append(line)
    return "\n".join(out_lines)


def clean(raw_text: str) -> str:
    """Deterministic, non-LLM preprocessing. Spoken transcripts get full ASR/filler cleanup;
    structured documents (BRDs, specs) only get whitespace/blank-line normalization, since they
    have no timestamps/filler speech to strip and the speech-cleanup regexes could clip prose."""
    text = raw_text.replace("\r\n", "\n")
    if looks_like_transcript(text):
        text = _TIMESTAMP_RE.sub("", text)
        text = _LAUGH_NOISE_RE.sub("", text)
        text = _SPEAKER_LABEL_RE.sub(lambda m: f"{m.group(1).strip()}: ", text)
        text = _FILLER_WORDS_RE.sub("", text)
        text = _WORD_REPEAT_RE.sub(r"\1", text)
        text = _dedupe_sentences(text)
    text = _WHITESPACE_RE.sub(" ", text)
    text = _BLANK_LINES_RE.sub("\n\n", text)
    lines = [line.strip() for line in text.split("\n")]
    lines = [line for line in lines if line and not re.fullmatch(r"[:\-\s]*", line)]
    return "\n".join(lines).strip()
