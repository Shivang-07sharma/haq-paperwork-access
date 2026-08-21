"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { FieldSpec, ProfileDto, QuestionDto, api } from "@/lib/api";
import { useApp } from "@/lib/store";
import { Icon, Progress, Spinner } from "@/components/ui";

const GROUP_ORDER = ["identity", "address", "household", "work", "bank", "declarations"];

export default function ProfilePage() {
  const { t, lang, profileId, ready } = useApp();
  const [profile, setProfile] = useState<ProfileDto | null>(null);
  const [specs, setSpecs] = useState<FieldSpec[]>([]);
  const [questions, setQuestions] = useState<QuestionDto[]>([]);
  const [draft, setDraft] = useState<Record<string, unknown>>({});
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  const load = useCallback(async () => {
    if (!profileId) return;
    setLoading(true);
    try {
      const [p, f, q] = await Promise.all([
        api.profile(profileId, lang),
        api.fields(lang),
        api.questions(profileId, lang),
      ]);
      setProfile(p);
      setSpecs(f);
      setQuestions(q);
      setDraft({});
    } finally {
      setLoading(false);
    }
  }, [profileId, lang]);

  useEffect(() => { void load(); }, [load]);

  const grouped = useMemo(() => {
    const out: Record<string, FieldSpec[]> = {};
    specs.forEach((s) => { (out[s.group] ||= []).push(s); });
    return out;
  }, [specs]);

  async function save(patch: Record<string, unknown>) {
    if (!profileId || Object.keys(patch).length === 0) return;
    setSaving(true);
    try {
      await api.updateProfile(profileId, lang, patch);
      await load();
    } finally {
      setSaving(false);
    }
  }

  if (!ready || loading) return <Spinner />;
  if (!profile) return null;

  function currentValue(name: string): unknown {
    return name in draft ? draft[name] : profile!.fields[name];
  }

  function provenance(name: string) {
    const src = profile!.field_sources[name];
    if (!src) return null;
    if (src.method === "manual") return t("profile.entered_by_you");
    return t("profile.from_document", { doc: t("doc." + (src.doc_type ?? "unknown")) });
  }

  return (
    <div className="space-y-6">
      <header>
        <h1 className="text-2xl font-bold">{t("profile.title")}</h1>
        <p className="text-lg text-ink-soft mt-2">{t("profile.help")}</p>
        <div className="mt-4">
          <p className="text-base font-semibold mb-1.5">
            {t("profile.completeness", { n: profile.filled_count, total: profile.total_count })}
          </p>
          <Progress percent={profile.completeness} />
        </div>
      </header>

      {questions.length > 0 && (
        <section className="card p-5 bg-indigo-light/50 border-indigo-mid/25">
          <h2 className="text-lg font-bold">{t("profile.questions_title")}</h2>
          <p className="text-base text-ink-soft mt-1">{t("profile.questions_help")}</p>
          <ul className="mt-4 space-y-4">
            {questions.slice(0, 4).map((q) => (
              <li key={q.name}>
                <p className="text-lg font-medium">{q.label}</p>
                <p className="text-sm text-indigo-deep font-semibold mb-2">
                  {t("upload.next_best", { doc: q.label, n: q.unlocks })}
                </p>
                <div className="flex flex-wrap gap-2">
                  {q.type === "boolean"
                    ? [true, false].map((v) => (
                        <button key={String(v)} className="btn-secondary" disabled={saving}
                          onClick={() => save({ [q.name]: v })}>
                          {v ? t("action.confirm") : t("action.deny")}
                        </button>
                      ))
                    : (q.options ?? []).map((opt) => (
                        <button key={opt} className="btn-secondary" disabled={saving}
                          onClick={() => save({ [q.name]: opt })}>
                          {q.option_labels?.[opt] ?? opt}
                        </button>
                      ))}
                </div>
              </li>
            ))}
          </ul>
        </section>
      )}

      {GROUP_ORDER.filter((g) => grouped[g]).map((group) => (
        <section key={group}>
          <h2 className="field-label mb-2">{group}</h2>
          <ul className="card divide-y divide-sand-line">
            {grouped[group].map((spec) => {
              const value = currentValue(spec.name);
              const source = provenance(spec.name);
              return (
                <li key={spec.name} className="p-4">
                  <label htmlFor={spec.name} className="block text-base font-medium">
                    {spec.label}
                    {spec.unit ? <span className="text-ink-faint"> ({spec.unit})</span> : null}
                  </label>
                  {source && (
                    <p className="text-sm text-ink-faint mt-0.5 flex items-center gap-1">
                      <Icon name="doc" className="w-3.5 h-3.5" />
                      {source}
                    </p>
                  )}

                  {spec.type === "choice" ? (
                    <select id={spec.name} className="input mt-2"
                      value={value === null || value === undefined ? "" : String(value)}
                      onChange={(e) => setDraft({ ...draft, [spec.name]: e.target.value || null })}>
                      <option value="">{t("profile.missing")}</option>
                      {(spec.options ?? []).map((opt) => (
                        <option key={opt} value={opt}>{spec.option_labels?.[opt] ?? opt}</option>
                      ))}
                    </select>
                  ) : spec.type === "boolean" ? (
                    <div className="flex gap-2 mt-2">
                      {[true, false].map((v) => (
                        <button key={String(v)} type="button"
                          onClick={() => setDraft({ ...draft, [spec.name]: v })}
                          aria-pressed={value === v}
                          className={"btn-secondary flex-1 " + (value === v ? "border-indigo-deep" : "")}>
                          {v ? t("action.confirm") : t("action.deny")}
                        </button>
                      ))}
                    </div>
                  ) : (
                    <input id={spec.name} className="input mt-2"
                      type={spec.type === "number" ? "number" : spec.type === "date" ? "date" : "text"}
                      inputMode={spec.type === "tel" ? "numeric" : undefined}
                      value={value === null || value === undefined ? "" : String(value)}
                      placeholder={t("profile.missing")}
                      onChange={(e) => {
                        const raw = e.target.value;
                        const next = spec.type === "number"
                          ? (raw === "" ? null : Number(raw))
                          : (raw === "" ? null : raw);
                        setDraft({ ...draft, [spec.name]: next });
                      }} />
                  )}
                </li>
              );
            })}
          </ul>
        </section>
      ))}

      <div className="sticky bottom-20 z-10">
        <button className="btn-primary w-full text-xl shadow-card"
          disabled={saving || Object.keys(draft).length === 0}
          onClick={() => save(draft)}>
          {saving ? t("upload.reading") : t("action.save")}
        </button>
      </div>
    </div>
  );
}
