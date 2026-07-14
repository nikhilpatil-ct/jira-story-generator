import logging

logger = logging.getLogger("pii_redactor")

ENTITIES = [
    "PERSON",
    "EMAIL_ADDRESS",
    "PHONE_NUMBER",
    "CREDIT_CARD",
    "US_SSN",
    "US_BANK_NUMBER",
    "IBAN_CODE",
    "IP_ADDRESS",
    "CRYPTO",
    "LOCATION",
]

_analyzer = None
_anonymizer = None
_unavailable_reason: str | None = None

try:
    from presidio_analyzer import AnalyzerEngine
    from presidio_analyzer.nlp_engine import NlpEngineProvider
    from presidio_anonymizer import AnonymizerEngine

    # Presidio defaults to en_core_web_lg (~400MB); pin to the small model we actually ship/install.
    _nlp_engine = NlpEngineProvider(
        nlp_configuration={
            "nlp_engine_name": "spacy",
            "models": [{"lang_code": "en", "model_name": "en_core_web_sm"}],
        }
    ).create_engine()
    _analyzer = AnalyzerEngine(nlp_engine=_nlp_engine, supported_languages=["en"])
    _anonymizer = AnonymizerEngine()
except Exception as exc:  # noqa: BLE001 - PII redaction is best-effort, never block the pipeline
    _unavailable_reason = str(exc)
    logger.warning("PII redaction unavailable, skipping: %s", exc)


def redact(text: str) -> tuple[str, list[str]]:
    """Detect and mask PII (names, emails, phone numbers, etc.) in transcript text.

    Returns (redacted_text, sorted list of entity types found). Falls back to returning the
    original text untouched if Presidio/its spaCy model isn't available, rather than failing
    the whole generation pipeline over an optional privacy pass.
    """
    if _analyzer is None or _anonymizer is None or not text.strip():
        return text, []

    from presidio_anonymizer.entities import OperatorConfig

    results = _analyzer.analyze(text=text, entities=ENTITIES, language="en")
    if not results:
        return text, []

    operators = {e: OperatorConfig("replace", {"new_value": f"<{e}>"}) for e in ENTITIES}
    anonymized = _anonymizer.anonymize(text=text, analyzer_results=results, operators=operators)
    entity_types = sorted({r.entity_type for r in results})
    return anonymized.text, entity_types
