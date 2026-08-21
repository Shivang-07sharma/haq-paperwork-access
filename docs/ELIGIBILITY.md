# Eligibility engine

Code: `backend/app/eligibility/`. Catalogue: `backend/data/schemes.json`.

Rules are data, never code. There is no `eval` anywhere in this module, so a
policy change is a JSON edit rather than a deploy, and a malformed rule fails
loudly at startup rather than quietly misjudging somebody.

## Three outcomes, not two

Every leaf rule evaluates to `pass`, `fail`, or `unknown`. `unknown` means the
fact needed to decide is absent.

| Rules tree | Exclusions | Scheme verdict |
|---|---|---|
| any leaf fails | anything | `not_eligible` |
| all pass | definitely triggered | `not_eligible`, with `excluded_by` |
| all pass | definitely not triggered | `eligible` |
| all pass | cannot be checked | `eligible`, with `assumed_not_excluded` |
| no fail, some unknown | not triggered | `need_more_info` |

The last row is the whole point. A first-time user with one photograph gets
`need_more_info` for most schemes, each carrying the exact list of what is
missing, instead of a wall of rejections.

An exclusion that cannot be checked does not block eligibility, because the
population this serves overwhelmingly does not pay income tax. But the
assumption is surfaced to the user rather than hidden.

## Facts available to rules

Built by `build_facts(profile)`. Two kinds:

**Stored** — every editable profile column: `full_name`, `date_of_birth`,
`gender`, `state`, `district`, `village_town`, `pincode`, `area_type`,
`annual_income`, `social_category`, `ration_card_type`, `occupation`,
`land_holding_acres`, `family_size`, `marital_status`, `education_level`,
`disability_percent`, `is_income_tax_payer`, `is_govt_employee`, `house_type`,
`has_lpg_connection`, `is_pregnant_or_lactating`, `has_bank_account`, `ifsc`,
`pan`, `mobile`.

**Derived** — computed at evaluation time:

| Fact | From | Note |
|---|---|---|
| `age` | `date_of_birth` | Whole years |
| `is_bpl` | `ration_card_type` in AAY, PHH, BPL | |
| `has_land` | `land_holding_acres > 0` | |

Derived facts stay `None` when the source is missing. Deriving `False` from
absent data would silently convert `unknown` into `fail`, which is the exact bug
this design exists to avoid.

## Rule syntax

A leaf:

```json
{ "field": "age", "op": ">=", "value": 60, "key": "rule.age_min", "args": { "n": 60 } }
```

| Property | Required | Purpose |
|---|---|---|
| `field` | yes | A fact name |
| `op` | yes | See operators below |
| `value` | depends | Not used by `is_true`, `is_false`, `exists` |
| `key` | recommended | i18n key for the human sentence |
| `args` | no | Interpolated into the sentence; `amount` is money-formatted |

Operators: `==`, `!=`, `in`, `not_in`, `>`, `>=`, `<`, `<=`, `is_true`,
`is_false`, `exists`.

Combinators: `all`, `any`, `not`.

```json
{
  "all": [
    { "field": "gender", "op": "==", "value": "female", "key": "rule.is_female" },
    { "any": [
      { "field": "is_bpl", "op": "is_true", "key": "rule.is_bpl" },
      { "field": "annual_income", "op": "<=", "value": 120000,
        "key": "rule.income_max", "args": { "amount": 120000 } }
    ]}
  ]
}
```

Two conventions that matter:

- **Empty `all` is `pass`** and **empty `any` is `fail`**, the mathematical
  identities. This is not pedantry: `"exclusions": { "any": [] }` means nothing
  disqualifies you, and an empty `any` returning `pass` would mark every scheme
  with no exclusions as excluded.
- **Comparison against a missing fact returns `unknown`**, never `False`.

## Anatomy of a scheme

```json
{
  "id": "ignoaps",
  "name":      { "en": "Old Age Pension (IGNOAPS)", "hi": "वृद्धावस्था पेंशन (IGNOAPS)" },
  "full_name": { "en": "Indira Gandhi National Old Age Pension Scheme", "hi": "..." },
  "department":{ "en": "Ministry of Rural Development (NSAP)", "hi": "..." },
  "category": "pension",
  "icon": "hand-coins",
  "benefit":  { "en": "A monthly pension paid into your bank account for life...", "hi": "..." },
  "benefit_amount_inr": 200,
  "benefit_period": "month",
  "rules": { "all": [
    { "field": "age", "op": ">=", "value": 60, "key": "rule.age_min", "args": { "n": 60 } },
    { "field": "is_bpl", "op": "is_true", "key": "rule.is_bpl" }
  ]},
  "exclusions": { "any": [] },
  "required_documents": ["aadhaar", "ration_card", "bank_passbook", "birth_certificate"],
  "apply_url": "https://nsap.nic.in",
  "apply_offline": { "en": "Gram Panchayat or the Block Development Office...", "hi": "..." },
  "processing_days": 45,
  "form_id": "nsap_form"
}
```

`benefit_period` is `month`, `year`, or `one_time`. `category` matters for
display: `health` and `insurance` are treated as cover rather than cash and are
never added into the yearly total. `form_id` must exist in `FORMS` in
`backend/app/forms/autofill.py`.

Language blocks fall back to `en` when a translation is absent.

## Ranking

`_score` orders the list so the most useful thing is first.

```
score = base + log10(amount * period_weight + 10) * 10 + confidence * 20

base           eligible 1000, need_more_info 500, not_eligible 0
period_weight  month 12, year 1, one_time 0.5
confidence     share of rules decided on real data
```

Benefit size is compressed logarithmically on purpose. A linear sum would bury a
six thousand rupee cash transfer that the person can actually collect underneath
a five lakh hospital cover they may never use. Within `need_more_info`, the
confidence term floats the schemes closest to a decision to the top.

## Turning gaps into actions

For a `need_more_info` verdict the engine collects the unknown fields and splits
them using `FIELD_SOURCES`:

- a field a document could supply becomes `documents_that_would_help`
- a field mapped to `self_declared` becomes `questions_to_ask`

`unlock_summary()` then aggregates across all sixteen schemes and returns which
single document settles the most. That is the source of the prompt *add your
bank passbook, it settles five more schemes*, and of the ranked question list at
`/api/profiles/{id}/questions`.

## Adding a scheme

1. Append an object to `backend/data/schemes.json`.
2. If a rule needs a fact that does not exist yet:
   - add the column to `Profile` in `backend/app/models.py`
   - add an entry to `FIELD_SPECS` in `backend/app/schemas.py` so it is editable
   - add it to `FIELD_SOURCES` in `eligibility/engine.py` so the app knows which
     document supplies it, or map it to `self_declared`
   - add `field.<name>` to every string bundle
   - add the column to the list in `build_facts`
3. Add any new rule sentence keys to `en.json` and the other bundles.
4. Add a `form_id` entry to `FORMS` if the scheme has its own form.
5. Restart. `load_catalog()` validates every operator and rejects duplicate ids.

Delete `backend/fed.db` if you changed `Profile`, since there is no migration
tool.

## Accuracy warning

These criteria are triage, not adjudication. They encode headline
central-government rules and deliberately omit state variations, SECC
deprivation codes and annual revisions. `_meta.note` in the catalogue says so,
and every screen carries a disclaimer that only the government office decides.

An error here misinforms somebody about a legal entitlement. Treat changes to
`schemes.json` as you would a change to billing code: cite the source, and have
someone else check it.
