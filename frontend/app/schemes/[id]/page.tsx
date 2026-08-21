"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { SchemeExplanation, api } from "@/lib/api";
import { useApp } from "@/lib/store";
import { Icon, Progress, SpeakButton, Spinner, StatusPill } from "@/components/ui";

/** One scheme, explained. This page is the product. */
export default function SchemeDetailPage() {
  const { t, lang, profileId, ready } = useApp();
  const params = useParams<{ id: string }>();
  const schemeId = params?.id;

  const [data, setData] = useState<SchemeExplanation | null>(null);
  const [loading, setLoading] = useState(true);
  const [applying, setApplying] = useState(false);

  const load = useCallback(async () => {
    if (!profileId || !schemeId) return;
    setLoading(true);
    try {
      setData(await api.scheme(profileId, schemeId, lang));
    } finally {
      setLoading(false);
    }
  }, [profileId, schemeId, lang]);

  useEffect(() => {
    void load();
  }, [load]);

  async function apply() {
    if (!profileId || !schemeId) return;
    setApplying(true);
    try {
      await api.createApplication(profileId, lang, schemeId);
      await load();
    } finally {
      setApplying(false);
    }
  }

  if (!ready || loading) return <Spinner />;
  if (!data) return <p className="text-lg">Not found.</p>;

  const app = data.application;

  return (
    <article className="space-y-5">
      <Link href="/schemes" className="btn-quiet -ml-3">
        <Icon name="arrow" className="w-5 h-5 rotate-180" />
        {t("action.back")}
      </Link>

      <header className="space-y-3">
        <StatusPill status={data.status} label={data.status_label} />
        <h1 className="text-3xl font-bold leading-tight">{data.name}</h1>
        <p className="text-base text-ink-soft">{data.full_name}</p>
        <p className="text-sm text-ink-faint">
          {t("explain.department", { department: data.department })}
        </p>
        <SpeakButton text={data.speech_text} className="-ml-3" />
      </header>

      <section className="card p-5">
        <h2 className="field-label">{data.headings.what_you_get}</h2>
        <p className="text-lg mt-2">{data.what_you_get}</p>
        {data.benefit_amount ? (
          <p className="text-2xl font-bold text-moss-deep mt-3">
            {data.benefit_amount_text}{" "}
            {["health", "insurance"].includes(data.category)
              ? t("schemes.cover_suffix")
              : data.benefit_period === "month"
                ? t("schemes.per_month")
                : data.benefit_period === "year"
                  ? t("schemes.per_year")
                  : ""}
          </p>
        ) : null}
      </section>

      {data.why_you_qualify.length > 0 && (
        <section className="card p-5">
          <h2 className="field-label">{data.headings.why_you_qualify}</h2>
          <ul className="mt-3 space-y-2.5">
            {data.why_you_qualify.map((r) => (
              <li key={r.field} className="flex gap-3 items-start">
                <Icon name="check" className="w-5 h-5 text-moss-mid shrink-0 mt-1" />
                <span className="text-lg">{r.text}</span>
              </li>
            ))}
          </ul>
        </section>
      )}

      {data.still_needed.length > 0 && (
        <section className="card p-5 border-amber-mid/35 bg-amber-light/40">
          <h2 className="field-label">{data.headings.still_needed}</h2>
          <ul className="mt-3 space-y-3">
            {data.still_needed.map((item) => (
              <li key={item.field} className="flex gap-3 items-start">
                <Icon name="question" className="w-5 h-5 text-amber-deep shrink-0 mt-1" />
                <div>
                  <p className="text-lg">{item.text}</p>
                  {item.document_hints.length > 0 ? (
                    <p className="text-sm text-ink-soft mt-0.5">
                      {item.document_hints.join(" / ")}
                    </p>
                  ) : (
                    <Link
                      href="/profile"
                      className="text-sm font-semibold text-indigo-deep underline"
                    >
                      {item.field_label}
                    </Link>
                  )}
                </div>
              </li>
            ))}
          </ul>
        </section>
      )}

      {data.why_not.length > 0 && (
        <section className="card p-5">
          <h2 className="field-label">{data.headings.why_not}</h2>
          <ul className="mt-3 space-y-2.5">
            {data.why_not.map((r, i) => (
              <li key={r.field + i} className="flex gap-3 items-start">
                <Icon name="cross" className="w-5 h-5 text-clay-mid shrink-0 mt-1" />
                <span className="text-lg">{r.text}</span>
              </li>
            ))}
          </ul>
        </section>
      )}

      {data.assumptions.length > 0 && (
        <section className="rounded-xl bg-sand-deep px-4 py-3">
          <p className="text-sm font-semibold text-ink-soft">{data.headings.assumption}</p>
          <ul className="mt-1.5 space-y-1">
            {data.assumptions.map((a) => (
              <li key={a.field} className="text-base text-ink-soft">
                - {a.text}
              </li>
            ))}
          </ul>
          <Link href="/profile" className="btn-quiet mt-1 -ml-3">
            {t("action.edit")}
          </Link>
        </section>
      )}

      {data.what_to_do.length > 0 && (
        <section className="card p-5">
          <h2 className="field-label">{data.headings.what_to_do}</h2>
          <ol className="mt-3 space-y-3">
            {data.what_to_do.map((step, i) => (
              <li key={i} className="flex gap-3 items-start">
                <span className="shrink-0 w-7 h-7 rounded-full bg-indigo-deep text-white grid place-items-center text-sm font-bold">
                  {i + 1}
                </span>
                <span className="text-lg">{step}</span>
              </li>
            ))}
          </ol>
          <p className="text-base text-ink-soft mt-4">{data.processing_time}</p>
        </section>
      )}

      {data.documents_needed.length > 0 && (
        <section className="card p-5">
          <h2 className="field-label">{data.headings.documents_needed}</h2>
          <ul className="mt-3 space-y-2">
            {data.documents_needed.map((d) => (
              <li key={d.doc_type} className="flex items-center gap-3">
                <Icon
                  name={d.have ? "check" : "cross"}
                  className={
                    "w-5 h-5 shrink-0 " + (d.have ? "text-moss-mid" : "text-clay-mid")
                  }
                />
                <span className="text-lg flex-1">{d.label}</span>
                <span className="text-sm text-ink-faint">
                  {d.have ? t("explain.you_have_it") : t("explain.you_need_it")}
                </span>
              </li>
            ))}
          </ul>
        </section>
      )}

      {data.status === "eligible" && (
        <section className="card p-5 space-y-4">
          {data.form_preview && (
            <div>
              <div className="flex items-baseline justify-between gap-3">
                <h2 className="field-label">{data.form_preview.title}</h2>
                <span className="text-base font-bold">
                  {t("applications.completion", {
                    percent: Math.round(data.form_preview.completion_percent),
                  })}
                </span>
              </div>
              <div className="mt-2">
                <Progress percent={data.form_preview.completion_percent} tone="moss" />
              </div>
              {data.form_preview.missing_required.length > 0 && (
                <p className="text-sm text-amber-deep mt-2">
                  {t("applications.missing_for_form")}:{" "}
                  {data.form_preview.missing_required.map((m) => m.label).join(", ")}
                </p>
              )}
            </div>
          )}

          {app ? (
            <div className="space-y-3">
              <p className="text-lg font-semibold">{app.status_label}</p>
              {app.reference_no && (
                <p className="text-base text-ink-soft">
                  {t("applications.reference")}:{" "}
                  <span className="font-mono">{app.reference_no}</span>
                </p>
              )}
              <div className="flex gap-3 flex-wrap">
                {app.has_form && (
                  <a
                    className="btn-secondary flex-1"
                    href={api.applicationFormUrl(app.id)}
                    target="_blank"
                    rel="noreferrer"
                  >
                    <Icon name="download" className="w-5 h-5" />
                    {t("action.download_form")}
                  </a>
                )}
                <Link href="/applications" className="btn-primary flex-1">
                  {t("nav.applications")}
                </Link>
              </div>
            </div>
          ) : (
            <button className="btn-primary w-full text-xl" onClick={apply} disabled={applying}>
              {applying ? t("upload.reading") : t("action.apply")}
            </button>
          )}
        </section>
      )}

      {data.apply_url && (
        <a
          href={data.apply_url}
          target="_blank"
          rel="noreferrer"
          className="block text-base text-indigo-deep underline break-all"
        >
          {t("explain.apply_online", { url: data.apply_url })}
        </a>
      )}

      <section>
        <h2 className="field-label">{data.headings.where_to_go}</h2>
        <p className="text-lg mt-2">{data.where_to_go}</p>
      </section>
    </article>
  );
}
