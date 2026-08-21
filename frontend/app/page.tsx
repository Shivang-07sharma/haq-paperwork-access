"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { SchemesResponse, api } from "@/lib/api";
import { useApp } from "@/lib/store";
import { Icon, Spinner } from "@/components/ui";

export default function HomePage() {
  const { t, lang, profileId, ready } = useApp();
  const [summary, setSummary] = useState<SchemesResponse["summary"] | null>(null);
  const [docCount, setDocCount] = useState(0);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!profileId) return;
    let cancelled = false;
    (async () => {
      try {
        const [schemes, docs] = await Promise.all([
          api.schemes(profileId, lang),
          api.documents(profileId, lang),
        ]);
        if (cancelled) return;
        setSummary(schemes.summary);
        setDocCount(docs.length);
      } catch {
        /* home still renders without the summary */
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, [profileId, lang]);

  if (!ready) return <Spinner />;

  const started = docCount > 0;

  return (
    <div className="space-y-6">
      <section>
        <p className="text-lg text-ink-soft">{t("home.greeting")}</p>
        <h1 className="text-3xl font-bold leading-tight mt-1">{t("schemes.title")}</h1>
        <p className="text-lg text-ink-soft mt-3">{t("home.intro")}</p>
      </section>

      {started && summary ? (
        <section className="card p-5">
          <div className="flex items-baseline gap-3 flex-wrap">
            <span className="text-4xl font-bold text-moss-deep">{summary.eligible}</span>
            <span className="text-lg font-semibold">
              {t("schemes.eligible_count", { n: summary.eligible })}
            </span>
          </div>
          {summary.annual_value > 0 && (
            <p className="text-lg text-ink-soft mt-2">
              {t("schemes.worth", { amount: summary.annual_value_text })}
            </p>
          )}
          {summary.cover_value > 0 && (
            <p className="text-base text-ink-soft mt-1">
              + {summary.cover_value_text} health and insurance cover
            </p>
          )}
          {summary.need_more_info > 0 && (
            <p className="text-base text-amber-deep mt-2 font-medium">
              {t("schemes.need_info_count", { n: summary.need_more_info })}
            </p>
          )}
          <Link href="/schemes" className="btn-primary w-full mt-4">
            {t("action.view_all")}
            <Icon name="arrow" className="w-5 h-5" />
          </Link>
        </section>
      ) : null}

      <Link href="/upload" className="btn-primary w-full text-xl">
        <Icon name="camera" className="w-6 h-6" />
        {started ? t("action.upload") : t("action.take_photo")}
      </Link>

      <ol className="space-y-3">
        {[
          { n: 1, title: "home.step1", help: "home.step1_help", icon: "camera" },
          { n: 2, title: "home.step2", help: "home.step2_help", icon: "doc" },
          { n: 3, title: "home.step3", help: "home.step3_help", icon: "gift" },
        ].map((step) => (
          <li key={step.n} className="card p-4 flex gap-4 items-start">
            <span className="shrink-0 w-11 h-11 rounded-full bg-indigo-light text-indigo-deep
                             grid place-items-center">
              <Icon name={step.icon} className="w-6 h-6" />
            </span>
            <div>
              <h2 className="text-lg font-bold">{t(step.title)}</h2>
              <p className="text-base text-ink-soft mt-0.5">{t(step.help)}</p>
            </div>
          </li>
        ))}
      </ol>

      <p className="text-sm text-ink-faint border-t border-sand-line pt-4">
        {t("app.disclaimer")}
      </p>
      {loading && !summary ? null : null}
    </div>
  );
}
