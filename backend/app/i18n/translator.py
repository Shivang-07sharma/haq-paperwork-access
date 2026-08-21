"""Translation and the vernacular explainer.

Two jobs live here.

`t()` is an ordinary key lookup with a fallback chain, but the fallback is
deliberately visible: a language that only partly covers the key set reports its
coverage so the UI can say so rather than quietly serving English under a Tamil
heading.

`explain()` is the part that matters. It converts a machine verdict -- a list of
rule outcomes -- into the answer a person actually came for: what this is, what
you get, why you qualify, and what to do on Monday morning. Every sentence is
built from short reusable phrases, so adding a language means translating one
flat bundle rather than rewriting sixteen scheme essays per language.
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from ..config import DEFAULT_LANGUAGE, LANGUAGES

STRINGS_DIR = Path(__file__).resolve().parent / "strings"


@lru_cache(maxsize=None)
def _load(lang: str) -> dict[str, str]:
    path = STRINGS_DIR / f"{lang}.json"
    if not path.exists():
        return {}
    try:
        with path.open(encoding="utf-8") as fh:
            return json.load(fh)
    except (json.JSONDecodeError, OSError):
        # A half-finished translation file must not take the whole app down.
        # The caller falls back to English and coverage reports it as missing.
        return {}


@lru_cache(maxsize=1)
def available_languages() -> list[dict]:
    """Every configured language plus how much of the key set it really covers."""
    base = _load(DEFAULT_LANGUAGE)
    total = len(base) or 1
    out = []
    for code, meta in LANGUAGES.items():
        strings = _load(code)
        coverage = round(len(set(strings) & set(base)) / total, 3)
        out.append(
            {
                "code": code,
                "label": meta["label"],
                "native": meta["native"],
                "tts": meta["tts"],
                "coverage": 1.0 if code == DEFAULT_LANGUAGE else coverage,
                "complete": coverage >= 0.98 or code == DEFAULT_LANGUAGE,
            }
        )
    return out


def strings_for(lang: str) -> dict[str, str]:
    """Full bundle for a language, English-backfilled, for the frontend."""
    merged = dict(_load(DEFAULT_LANGUAGE))
    merged.update(_load(lang))
    return merged


def t(key: str, lang: str = DEFAULT_LANGUAGE, **args: Any) -> str:
    """Look up a key, falling back to English and finally to the key itself."""
    template = _load(lang).get(key) or _load(DEFAULT_LANGUAGE).get(key) or key
    if not args:
        return template
    try:
        return template.format(**args)
    except (KeyError, IndexError, ValueError):
        # A malformed placeholder should degrade to readable text, not explode.
        return template


def pick(value: Any, lang: str) -> str:
    """Resolve a {lang: text} block from the scheme catalogue."""
    if isinstance(value, dict):
        return value.get(lang) or value.get(DEFAULT_LANGUAGE) or ""
    return value or ""


def money(amount: float | int | None, lang: str = DEFAULT_LANGUAGE) -> str:
    """Format rupees the way Indian readers expect: lakh and crore, not millions."""
    if amount is None:
        return ""
    amount = float(amount)
    if amount >= 10_000_000:
        return f"Rs {amount / 10_000_000:.2f}".rstrip("0").rstrip(".") + " crore"
    if amount >= 100_000:
        return f"Rs {amount / 100_000:.2f}".rstrip("0").rstrip(".") + " lakh"
    # Indian digit grouping: 1,20,000 rather than 120,000.
    whole = int(round(amount))
    text = str(whole)
    if len(text) > 3:
        head, tail = text[:-3], text[-3:]
        groups = []
        while len(head) > 2:
            groups.insert(0, head[-2:])
            head = head[:-2]
        if head:
            groups.insert(0, head)
        text = ",".join(groups + [tail])
    return f"Rs {text}"


# --------------------------------------------------------------------------
# the explainer
# --------------------------------------------------------------------------

def _phrase(outcome, lang: str) -> str:
    args = dict(outcome.args or {})
    if "amount" in args:
        args["amount"] = money(args["amount"], lang)
    return t(outcome.key, lang, **args)


def explain(
    scheme: dict,
    verdict,
    lang: str = DEFAULT_LANGUAGE,
    owned_doc_types: set[str] | None = None,
) -> dict:
    """Turn one scheme verdict into a page a person can act on."""
    owned = owned_doc_types or set()

    name = pick(scheme.get("name"), lang)
    full_name = pick(scheme.get("full_name"), lang)
    department = pick(scheme.get("department"), lang)
    where = pick(scheme.get("apply_offline"), lang)

    why_you_qualify = [
        {"text": _phrase(o, lang), "field": o.field} for o in verdict.passed
    ]
    why_not = [{"text": _phrase(o, lang), "field": o.field} for o in verdict.failed]
    blocked = [{"text": _phrase(o, lang), "field": o.field} for o in verdict.excluded_by]

    still_needed = []
    for outcome in verdict.unknown:
        hints = [t(f"doc.{doc}", lang) for doc in _docs_for_field(outcome.field)]
        still_needed.append(
            {
                "text": _phrase(outcome, lang),
                "field": outcome.field,
                "field_label": t(f"field.{outcome.field}", lang),
                "document_hints": hints,
            }
        )

    assumptions = [
        {"text": _phrase(o, lang), "field": o.field} for o in verdict.assumed_not_excluded
    ]

    documents_needed = [
        {"doc_type": doc, "label": t(f"doc.{doc}", lang), "have": doc in owned}
        for doc in scheme.get("required_documents", [])
    ]

    steps = _steps(scheme, verdict, lang, where)

    payload = {
        "scheme_id": scheme["id"],
        "name": name,
        "full_name": full_name,
        "department": department,
        "category": scheme.get("category"),
        "icon": scheme.get("icon"),
        "status": verdict.status,
        "status_label": t(f"status.{verdict.status}", lang),
        "status_short": t(f"status.{verdict.status}_short", lang),
        "confidence": verdict.confidence,
        "score": verdict.score,

        "headings": {
            "what_it_is": t("explain.what_it_is", lang),
            "what_you_get": t("explain.what_you_get", lang),
            "why_you_qualify": t("explain.why_you_qualify", lang),
            "why_not": t("explain.why_not", lang),
            "still_needed": t("explain.still_needed", lang),
            "what_to_do": t("explain.what_to_do", lang),
            "documents_needed": t("explain.documents_needed", lang),
            "where_to_go": t("explain.where_to_go", lang),
            "assumption": t("explain.assumption", lang),
        },

        "what_it_is": full_name or name,
        "what_you_get": pick(scheme.get("benefit"), lang),
        "benefit_amount": scheme.get("benefit_amount_inr"),
        "benefit_amount_text": money(scheme.get("benefit_amount_inr"), lang),
        "benefit_period": scheme.get("benefit_period"),
        "why_you_qualify": why_you_qualify,
        "why_not": why_not + blocked,
        "still_needed": still_needed,
        "assumptions": assumptions,
        "what_to_do": steps,
        "documents_needed": documents_needed,
        "where_to_go": where,
        "apply_url": scheme.get("apply_url"),
        "processing_time": t(
            "explain.processing_time", lang, days=scheme.get("processing_days", 30)
        ),
        "missing_fields": verdict.missing_fields,
        "documents_that_would_help": [
            {"doc_type": d, "label": t(f"doc.{d}", lang)}
            for d in verdict.documents_that_would_help
        ],
    }
    payload["speech_text"] = _speech(payload, lang)
    return payload


def _docs_for_field(field_name: str) -> list[str]:
    from ..eligibility.engine import FIELD_SOURCES

    return [d for d in FIELD_SOURCES.get(field_name, []) if d != "self_declared"]


def _steps(scheme: dict, verdict, lang: str, where: str) -> list[str]:
    """The concrete sequence, which differs by verdict rather than being generic."""
    from ..eligibility.engine import ELIGIBLE, NEED_MORE_INFO

    steps: list[str] = []

    if verdict.status == NEED_MORE_INFO:
        # Name the specific gap. "Answer a few questions" is not an instruction;
        # "Tell us one thing: marital status" is.
        for doc in verdict.documents_that_would_help[:2]:
            steps.append(t("step.bring_document", lang, doc=t(f"doc.{doc}", lang)))
        for field_name in verdict.questions_to_ask[:2]:
            steps.append(
                t("step.answer_question", lang, field=t(f"field.{field_name}", lang))
            )
        return steps or [t("step.check_documents", lang)]

    if verdict.status != ELIGIBLE:
        return []

    steps.append(t("step.check_documents", lang))
    if where:
        # apply_offline is already a complete sentence naming the office, so it
        # is used as-is. Wrapping it in "Go to {place}." produced doubled full
        # stops and a capitalised mid-sentence word.
        steps.append(where)
    steps.append(t("step.submit_form", lang))
    steps.append(t("step.keep_receipt", lang))
    steps.append(t("step.track_here", lang))
    return steps


def _speech(payload: dict, lang: str) -> str:
    """One flat string for the browser speech synthesiser.

    Read aloud, bullet lists need joining words or they run together, so the
    reasons are stitched into sentences rather than dumped as fragments.
    """
    parts = [payload["name"], payload["status_label"] + "."]

    if payload["what_you_get"]:
        parts.append(payload["headings"]["what_you_get"] + ": " + payload["what_you_get"])

    if payload["why_you_qualify"]:
        reasons = ". ".join(item["text"] for item in payload["why_you_qualify"])
        parts.append(payload["headings"]["why_you_qualify"] + ": " + reasons + ".")

    if payload["still_needed"]:
        reasons = ". ".join(item["text"] for item in payload["still_needed"])
        parts.append(payload["headings"]["still_needed"] + ": " + reasons + ".")

    if payload["why_not"]:
        reasons = ". ".join(item["text"] for item in payload["why_not"])
        parts.append(payload["headings"]["why_not"] + ": " + reasons + ".")

    if payload["what_to_do"]:
        parts.append(payload["headings"]["what_to_do"] + ": " + " ".join(payload["what_to_do"]))

    return " ".join(p for p in parts if p)
