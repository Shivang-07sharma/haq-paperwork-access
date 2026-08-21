"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { SchemeStatus, SchemesResponse, api } from "@/lib/api";
import { useApp } from "@/lib/store";
import { SchemeCard } from "@/components/SchemeCard";
import { Empty, Icon, Spinner } from "@/components/ui";

type Filter = "all" | SchemeStatus;

export default function SchemesPage() {
  const { t, lang, profileId, ready } = useApp();
  const [data, setData] = useState<SchemesResponse | null>(null);
  const [filter, setFilter] = useState<Filter>("all");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!profileId) return;
    let cancelled = false;
    setLoading(true);
    api.schemes(profileId, lang)
      .then((res) => { if (!cancelled) setData(res); })
      .catch(() => { if (!cancelled) setData(null); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [profileId, lang]);

  const shown = useMemo(() => {
    if (!data) return [];
    return filter === "all" ? data.schemes : data.schemes.filter((s) => s.status === filter);
  }, [data, filter]);

  if (!ready || loading) return <Spinner />;
  if (!data) return <Empty text={t("schemes.none_yet")} />;

  const { summary } = data;
  const tabs: { id: Filter; label: string; count: number }[] = [
    { id: "all", label: t("schemes.filter_all"), count: data.schemes.length },
    { id: "eligible", label: t("status.eligible_short"), count: summary.eligible },
    { id: "need_more_info", label: t("status.need_more_info_short"), count: summary.need_more_info },
    { id: "not_eligible", label: t("status.not_eligible_short"), count: summary.not_eligible },
  ];

  return (
    <div className="space-y-5">
      <header>
        <h1 className="text-2xl font-bold">{t("schemes.title")}</h1>
        {summary.eligible > 0 ? (
          <div className="mt-3 card p-4">
            <p className="text-lg font-semibold">
              {t("schemes.eligible_count", { n: summary.eligible })}
            </p>
            {summary.annual_value > 0 && (
              <p className="text-2xl font-bold text-moss-deep mt-1">
                {t("schemes.worth", { amount: summary.annual_value_text })}
              </p>
            )}
            {summary.cover_value > 0 && (
              <p className="text-base text-ink-soft mt-1">
                + {summary.cover_value_text} health and insurance cover
              </p>
            )}
          </div>
        ) : (
          <p className="text-lg text-ink-soft mt-2">{t("schemes.none_yet")}</p>
        )}
      </header>

      {data.next_documents.length > 0 && (
        <Link href="/upload"
          className="card p-4 flex items-center gap-3 bg-indigo-light border-indigo-mid/25">
          <Icon name="camera" className="w-6 h-6 text-indigo-deep shrink-0" />
          <span className="text-base text-indigo-deep flex-1">
            {t("upload.next_best", {
              doc: data.next_documents[0].label,
              n: data.next_documents[0].unlocks,
            })}
          </span>
          <Icon name="arrow" className="w-5 h-5 text-indigo-deep shrink-0" />
        </Link>
      )}

      <div className="flex gap-2 overflow-x-auto pb-1" role="tablist">
        {tabs.map((tab) => (
          <button key={tab.id} role="tab" aria-selected={filter === tab.id}
            onClick={() => setFilter(tab.id)}
            className={`chip min-h-[44px] px-4 whitespace-nowrap border-2 ${
              filter === tab.id
                ? "bg-indigo-deep text-white border-indigo-deep"
                : "bg-white text-ink-soft border-sand-line"
            }`}>
            {tab.label} ({tab.count})
          </button>
        ))}
      </div>

      {shown.length === 0 ? (
        <Empty text={t("schemes.none_yet")} />
      ) : (
        <ul className="space-y-3">
          {shown.map((s) => (
            <li key={s.scheme_id}><SchemeCard scheme={s} /></li>
          ))}
        </ul>
      )}

      <p className="text-sm text-ink-faint border-t border-sand-line pt-4">{data.disclaimer}</p>
    </div>
  );
}
