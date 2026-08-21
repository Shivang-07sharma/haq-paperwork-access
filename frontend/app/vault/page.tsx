"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { VaultResponse, api } from "@/lib/api";
import { useApp } from "@/lib/store";
import { ConfidenceDot, Empty, Icon, Spinner } from "@/components/ui";

const STATE_STYLE: Record<string, string> = {
  expired: "bg-clay-light text-clay-deep",
  expiring_soon: "bg-amber-light text-amber-deep",
  valid: "bg-moss-light text-moss-deep",
  no_expiry: "bg-sand-deep text-ink-soft",
};

export default function VaultPage() {
  const { t, lang, ttsLocale, profileId, ready } = useApp();
  const [data, setData] = useState<VaultResponse | null>(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    if (!profileId) return;
    setLoading(true);
    try {
      setData(await api.vault(profileId, lang));
    } finally {
      setLoading(false);
    }
  }, [profileId, lang]);

  useEffect(() => { void load(); }, [load]);

  async function dismiss(id: number) {
    await api.completeReminder(id);
    await load();
  }

  async function remove(id: number) {
    await api.deleteDocument(id);
    await load();
  }

  if (!ready || loading) return <Spinner />;
  if (!data) return <Empty text={t("vault.empty")} />;

  function stateLabel(state: string, expiry: string | null, daysLeft: number | null) {
    if (state === "expired" && expiry) return t("vault.expired", { date: expiry });
    if (state === "expiring_soon" && daysLeft !== null)
      return t("vault.expiring_soon", { days: daysLeft });
    if (state === "valid" && expiry) return t("vault.expires_on", { date: expiry });
    return t("vault.no_expiry");
  }

  return (
    <div className="space-y-5">
      <header>
        <h1 className="text-2xl font-bold">{t("vault.title")}</h1>
        <p className="text-lg text-ink-soft mt-2">{t("vault.help")}</p>
      </header>

      <section>
        <h2 className="field-label mb-2">{t("vault.reminders")}</h2>
        {data.reminders.length === 0 ? (
          <p className="text-base text-ink-soft">{t("vault.no_reminders")}</p>
        ) : (
          <ul className="space-y-2">
            {data.reminders.map((r) => (
              <li key={r.id} className="card p-4 flex items-start gap-3 border-amber-mid/35">
                <Icon name="alert" className="w-5 h-5 text-amber-deep shrink-0 mt-1" />
                <p className="text-base flex-1">{r.text}</p>
                <button className="btn-quiet shrink-0" onClick={() => dismiss(r.id)}>
                  {t("action.mark_done")}
                </button>
              </li>
            ))}
          </ul>
        )}
      </section>

      <section>
        <div className="flex items-center justify-between mb-2">
          <h2 className="field-label">{t("nav.upload")}</h2>
          <Link href="/upload" className="btn-quiet">
            <Icon name="camera" className="w-5 h-5" />
            {t("action.upload")}
          </Link>
        </div>

        {data.documents.length === 0 ? (
          <Empty text={t("vault.empty")} />
        ) : (
          <ul className="space-y-3">
            {data.documents.map((d) => (
              <li key={d.id} className="card p-4">
                <div className="flex items-start gap-3">
                  <Icon name="doc" className="w-6 h-6 text-ink-faint shrink-0 mt-0.5" />
                  <div className="min-w-0 flex-1">
                    <h3 className="text-lg font-bold">{d.label}</h3>
                    {d.number_masked && (
                      <p className="text-base font-mono text-ink-soft">{d.number_masked}</p>
                    )}
                    <p className="text-sm text-ink-faint mt-1">
                      {d.uploaded_at
                        ? t("vault.added_on", {
                            date: new Date(d.uploaded_at).toLocaleDateString(ttsLocale),
                          })
                        : ""}
                    </p>
                  </div>
                  <ConfidenceDot value={d.ocr_confidence} />
                </div>

                <div className="flex flex-wrap items-center gap-2 mt-3">
                  <span className={"chip " + STATE_STYLE[d.state]}>
                    {stateLabel(d.state, d.expiry_date, d.days_left)}
                  </span>
                  <a className="btn-quiet ml-auto" href={api.documentFileUrl(d.id)}
                    target="_blank" rel="noreferrer">
                    {t("action.view_all")}
                  </a>
                  <button className="btn-quiet text-clay-deep" onClick={() => remove(d.id)}>
                    <Icon name="cross" className="w-4 h-4" />
                  </button>
                </div>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}
