"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { ApplicationDto, api } from "@/lib/api";
import { useApp } from "@/lib/store";
import { Empty, Icon, Progress, Spinner } from "@/components/ui";

// Statuses a person can set themselves, in the order an application moves.
const NEXT_STEPS: Record<string, string[]> = {
  draft: ["submitted"],
  submitted: ["under_review", "documents_requested", "approved", "rejected"],
  under_review: ["documents_requested", "approved", "rejected"],
  documents_requested: ["under_review", "rejected"],
  approved: [],
  rejected: ["submitted"],
};

const TONE: Record<string, string> = {
  approved: "bg-moss-light text-moss-deep",
  rejected: "bg-clay-light text-clay-deep",
  documents_requested: "bg-amber-light text-amber-deep",
};

export default function ApplicationsPage() {
  const { t, lang, ttsLocale, profileId, ready } = useApp();
  const [apps, setApps] = useState<ApplicationDto[]>([]);
  const [loading, setLoading] = useState(true);
  const [pending, setPending] = useState<number | null>(null);

  const load = useCallback(async () => {
    if (!profileId) return;
    setLoading(true);
    try {
      setApps(await api.applications(profileId, lang));
    } finally {
      setLoading(false);
    }
  }, [profileId, lang]);

  useEffect(() => { void load(); }, [load]);

  async function move(app: ApplicationDto, status: string) {
    setPending(app.id);
    try {
      await api.setApplicationStatus(app.id, lang, status);
      await load();
    } finally {
      setPending(null);
    }
  }

  if (!ready || loading) return <Spinner />;

  return (
    <div className="space-y-5">
      <h1 className="text-2xl font-bold">{t("applications.title")}</h1>

      {apps.length === 0 ? (
        <>
          <Empty text={t("applications.empty")} />
          <Link href="/schemes" className="btn-primary w-full">{t("nav.schemes")}</Link>
        </>
      ) : (
        <ul className="space-y-4">
          {apps.map((app) => (
            <li key={app.id} className="card p-5 space-y-4">
              <div className="flex items-start gap-3">
                <div className="min-w-0 flex-1">
                  <Link href={"/schemes/" + app.scheme_id}
                    className="text-lg font-bold hover:underline">
                    {app.scheme_name}
                  </Link>
                  {app.reference_no && (
                    <p className="text-sm text-ink-soft mt-1">
                      {t("applications.reference")}:{" "}
                      <span className="font-mono">{app.reference_no}</span>
                    </p>
                  )}
                </div>
                <span className={"chip " + (TONE[app.status] ?? "bg-sand-deep text-ink-soft")}>
                  {app.status_label}
                </span>
              </div>

              <div>
                <div className="flex justify-between text-sm text-ink-soft mb-1.5">
                  <span>{t("applications.completion", {
                    percent: Math.round(app.completion_percent),
                  })}</span>
                  {app.days_waiting !== null && (
                    <span className="flex items-center gap-1">
                      <Icon name="clock" className="w-4 h-4" />
                      {app.days_waiting} days
                    </span>
                  )}
                </div>
                <Progress percent={app.completion_percent}
                  tone={app.completion_percent >= 100 ? "moss" : "indigo"} />
                {app.missing_fields.length > 0 && (
                  <p className="text-sm text-amber-deep mt-2">
                    {t("applications.missing_for_form")}:{" "}
                    {app.missing_fields.map((m) => m.label).join(", ")}
                  </p>
                )}
              </div>

              {app.events.length > 0 && (
                <ol className="border-l-2 border-sand-line pl-4 space-y-2">
                  {app.events.map((e, i) => (
                    <li key={i} className="text-base">
                      <span className="font-semibold">{e.status_label}</span>
                      {e.at && (
                        <span className="text-sm text-ink-faint ml-2">
                          {new Date(e.at).toLocaleDateString(ttsLocale)}
                        </span>
                      )}
                      {e.note && <p className="text-sm text-ink-soft">{e.note}</p>}
                    </li>
                  ))}
                </ol>
              )}

              <div className="flex flex-wrap gap-2">
                {app.has_form && (
                  <a className="btn-secondary" href={api.applicationFormUrl(app.id)}
                    target="_blank" rel="noreferrer">
                    <Icon name="download" className="w-5 h-5" />
                    {t("action.download_form")}
                  </a>
                )}
                {(NEXT_STEPS[app.status] ?? []).map((status) => (
                  <button key={status} className="btn-secondary" disabled={pending === app.id}
                    onClick={() => move(app, status)}>
                    {t("app_status." + status)}
                  </button>
                ))}
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
