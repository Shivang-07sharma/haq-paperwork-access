"""Declarative eligibility evaluation.

The important design decision is that a rule has **three** outcomes, not two:
pass, fail, and unknown. A binary engine has to treat "we have no income
certificate" as "you do not qualify", which is exactly the failure mode that
keeps people away from benefits they are entitled to. Here an unmet rule with no
data becomes a question to ask or a document to fetch, and the scheme is
reported as need_more_info rather than rejected.

Rules are data, never code -- there is no eval anywhere in this module, so a new
scheme is a JSON edit rather than a deploy.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import date
from typing import Any

PASS = "pass"
FAIL = "fail"
UNKNOWN = "unknown"

ELIGIBLE = "eligible"
NOT_ELIGIBLE = "not_eligible"
NEED_MORE_INFO = "need_more_info"

# Which document would supply a missing field. Fields answered by asking the
# person directly map to self_declared so the UI shows a question, not an upload.
FIELD_SOURCES: dict[str, list[str]] = {
    "date_of_birth": ["aadhaar", "voter_id", "birth_certificate"],
    "age": ["aadhaar", "voter_id", "birth_certificate"],
    "gender": ["aadhaar", "voter_id"],
    "full_name": ["aadhaar", "ration_card"],
    "annual_income": ["income_certificate"],
    "social_category": ["caste_certificate"],
    "ration_card_type": ["ration_card"],
    "is_bpl": ["ration_card"],
    "family_size": ["ration_card"],
    "land_holding_acres": ["land_record"],
    "has_land": ["land_record"],
    "has_bank_account": ["bank_passbook"],
    "ifsc": ["bank_passbook"],
    "disability_percent": ["disability_certificate"],
    "area_type": ["job_card", "ration_card"],
    "state": ["aadhaar", "domicile_certificate"],
    "district": ["aadhaar", "ration_card"],
    "pan": ["pan"],
    "marital_status": ["self_declared"],
    "house_type": ["self_declared"],
    "has_lpg_connection": ["self_declared"],
    "is_pregnant_or_lactating": ["self_declared"],
    "occupation": ["self_declared"],
    "education_level": ["self_declared"],
    "is_income_tax_payer": ["self_declared"],
    "is_govt_employee": ["self_declared"],
}


@dataclass
class RuleOutcome:
    key: str
    field: str
    status: str
    args: dict = field(default_factory=dict)
    actual: Any = None
    expected: Any = None


@dataclass
class SchemeVerdict:
    scheme_id: str
    status: str
    score: float = 0.0
    passed: list[RuleOutcome] = field(default_factory=list)
    failed: list[RuleOutcome] = field(default_factory=list)
    unknown: list[RuleOutcome] = field(default_factory=list)
    excluded_by: list[RuleOutcome] = field(default_factory=list)
    # Exclusions we could not check. We do not let these block a result -- most
    # people this serves are plainly not income tax payers -- but the UI must
    # show them as an assumption rather than pretend the check was made.
    assumed_not_excluded: list[RuleOutcome] = field(default_factory=list)
    missing_fields: list[str] = field(default_factory=list)
    documents_that_would_help: list[str] = field(default_factory=list)
    questions_to_ask: list[str] = field(default_factory=list)

    @property
    def confidence(self) -> float:
        """How much of the decision rests on data we actually have."""
        total = len(self.passed) + len(self.failed) + len(self.unknown)
        return round((len(self.passed) + len(self.failed)) / total, 3) if total else 0.0


# --------------------------------------------------------------------------
# derived fields
# --------------------------------------------------------------------------

def _age_from(dob: date | None, today: date | None = None) -> int | None:
    if not dob:
        return None
    today = today or date.today()
    return today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))


def build_facts(profile: Any, today: date | None = None) -> dict[str, Any]:
    """Flatten a profile into the fact dictionary rules are written against.

    Derived facts are only set when the underlying data exists. Deriving False
    from absent data would silently turn unknown into fail.
    """
    facts: dict[str, Any] = {}

    for column in (
        "full_name", "gender", "mobile", "state", "district", "village_town",
        "pincode", "area_type", "annual_income", "social_category",
        "ration_card_type", "occupation", "land_holding_acres", "family_size",
        "marital_status", "education_level", "disability_percent",
        "is_income_tax_payer", "is_govt_employee", "house_type",
        "has_lpg_connection", "is_pregnant_or_lactating", "has_bank_account",
        "ifsc", "pan", "date_of_birth",
    ):
        facts[column] = getattr(profile, column, None)

    facts["age"] = _age_from(facts.get("date_of_birth"), today)

    ration = facts.get("ration_card_type")
    facts["is_bpl"] = ration in {"AAY", "PHH", "BPL"} if ration else None

    land = facts.get("land_holding_acres")
    facts["has_land"] = land > 0 if land is not None else None

    return facts


# --------------------------------------------------------------------------
# rule evaluation
# --------------------------------------------------------------------------

def _compare(op: str, actual: Any, expected: Any) -> bool | None:
    """Return the comparison result, or None when it cannot be decided."""
    if op in {"is_true", "is_false"}:
        if actual is None:
            return None
        return bool(actual) if op == "is_true" else not bool(actual)

    if op == "exists":
        return actual is not None

    if actual is None:
        return None

    try:
        if op == "==":
            return actual == expected
        if op == "!=":
            return actual != expected
        if op == "in":
            return actual in expected
        if op == "not_in":
            return actual not in expected
        if op == ">":
            return float(actual) > float(expected)
        if op == ">=":
            return float(actual) >= float(expected)
        if op == "<":
            return float(actual) < float(expected)
        if op == "<=":
            return float(actual) <= float(expected)
    except (TypeError, ValueError):
        return None

    raise ValueError(f"unsupported operator: {op}")


def _eval_node(node: dict, facts: dict, out: list[RuleOutcome]) -> str:
    """Evaluate one rule node, appending leaf outcomes to out."""
    if "all" in node:
        results = [_eval_node(child, facts, out) for child in node["all"]]
        if any(r == FAIL for r in results):
            return FAIL                      # one hard failure sinks an AND
        if any(r == UNKNOWN for r in results):
            return UNKNOWN
        return PASS

    if "any" in node:
        children = node["any"]
        if not children:
            # Identity of OR is false. This matters most for exclusions: an
            # empty exclusion list means nothing disqualifies you, so it must
            # not evaluate as "triggered".
            return FAIL
        results = [_eval_node(child, facts, out) for child in children]
        if any(r == PASS for r in results):
            return PASS                      # one hit is enough for an OR
        if any(r == UNKNOWN for r in results):
            return UNKNOWN
        return FAIL

    if "not" in node:
        inner = _eval_node(node["not"], facts, out)
        if inner == PASS:
            return FAIL
        if inner == FAIL:
            return PASS
        return UNKNOWN

    # leaf
    field_name = node["field"]
    actual = facts.get(field_name)
    verdict = _compare(node["op"], actual, node.get("value"))
    status = UNKNOWN if verdict is None else (PASS if verdict else FAIL)

    out.append(
        RuleOutcome(
            key=node.get("key", f"rule.{field_name}"),
            field=field_name,
            status=status,
            args=node.get("args", {}),
            actual=actual.isoformat() if isinstance(actual, date) else actual,
            expected=node.get("value"),
        )
    )
    return status


def evaluate_scheme(scheme: dict, facts: dict) -> SchemeVerdict:
    """Decide one scheme against one set of facts."""
    outcomes: list[RuleOutcome] = []
    rules_status = _eval_node(scheme.get("rules") or {"all": []}, facts, outcomes)

    exclusion_outcomes: list[RuleOutcome] = []
    exclusions = scheme.get("exclusions") or {"any": []}
    exclusion_status = _eval_node(exclusions, facts, exclusion_outcomes)

    verdict = SchemeVerdict(scheme_id=scheme["id"], status=NOT_ELIGIBLE)
    verdict.passed = [o for o in outcomes if o.status == PASS]
    verdict.failed = [o for o in outcomes if o.status == FAIL]
    verdict.unknown = [o for o in outcomes if o.status == UNKNOWN]

    # An exclusion only bites when it definitely fires.
    if exclusion_status == PASS:
        verdict.status = NOT_ELIGIBLE
        verdict.excluded_by = [o for o in exclusion_outcomes if o.status == PASS]
    elif rules_status == PASS:
        verdict.status = ELIGIBLE
        verdict.assumed_not_excluded = [
            o for o in exclusion_outcomes if o.status == UNKNOWN
        ]
    elif rules_status == UNKNOWN:
        verdict.status = NEED_MORE_INFO
    else:
        verdict.status = NOT_ELIGIBLE

    # Only chase data that could still change the answer.
    if verdict.status == NEED_MORE_INFO:
        missing = {o.field for o in verdict.unknown}
        missing |= {o.field for o in exclusion_outcomes if o.status == UNKNOWN}
        verdict.missing_fields = sorted(missing)

        docs: list[str] = []
        questions: list[str] = []
        for field_name in verdict.missing_fields:
            for source in FIELD_SOURCES.get(field_name, []):
                if source == "self_declared":
                    if field_name not in questions:
                        questions.append(field_name)
                elif source not in docs:
                    docs.append(source)
        verdict.documents_that_would_help = docs
        verdict.questions_to_ask = questions

    verdict.score = _score(scheme, verdict)
    return verdict


def _score(scheme: dict, verdict: SchemeVerdict) -> float:
    """Rank order: certain money first, then near-misses, then rejections.

    Benefit size is compressed logarithmically so a Rs 5 lakh health cover does
    not bury a Rs 6,000 cash transfer that the person can actually collect.
    """
    base = {ELIGIBLE: 1000.0, NEED_MORE_INFO: 500.0, NOT_ELIGIBLE: 0.0}[verdict.status]
    amount = float(scheme.get("benefit_amount_inr") or 0)
    period_weight = {"month": 12.0, "year": 1.0, "one_time": 0.5}.get(
        scheme.get("benefit_period", "year"), 1.0
    )
    value = math.log10(amount * period_weight + 10.0) * 10.0

    # Among need_more_info, surface the ones closest to a decision.
    proximity = verdict.confidence * 20.0
    return round(base + value + proximity, 3)


def evaluate_all(schemes: list[dict], facts: dict) -> list[SchemeVerdict]:
    verdicts = [evaluate_scheme(scheme, facts) for scheme in schemes]
    verdicts.sort(key=lambda v: v.score, reverse=True)
    return verdicts


def unlock_summary(verdicts: list[SchemeVerdict]) -> list[dict]:
    """Which single document would settle the most undecided schemes.

    This drives the one prompt that matters on the upload screen: not "upload
    your documents" but "add your ration card to settle four more schemes".
    """
    tally: dict[str, set[str]] = {}
    for verdict in verdicts:
        if verdict.status != NEED_MORE_INFO:
            continue
        for doc in verdict.documents_that_would_help:
            tally.setdefault(doc, set()).add(verdict.scheme_id)

    return sorted(
        (
            {"doc_type": doc, "unlocks": len(ids), "scheme_ids": sorted(ids)}
            for doc, ids in tally.items()
        ),
        key=lambda row: row["unlocks"],
        reverse=True,
    )
