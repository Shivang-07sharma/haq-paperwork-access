"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { DocumentDto, UploadResult, api } from "@/lib/api";
import { useApp } from "@/lib/store";
import { ConfidenceDot, Empty, Icon, Spinner } from "@/components/ui";

export default function UploadPage() {
  const { t, lang, profileId, ready } = useApp();
  const fileInput = useRef<HTMLInputElement>(null);
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<UploadResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [docs, setDocs] = useState<DocumentDto[]>([]);
  const [docTypes, setDocTypes] = useState<{ doc_type: string; label: string }[]>([]);
  const [override, setOverride] = useState("");

  useEffect(() => {
    if (!profileId) return;
    api.documents(profileId, lang).then(setDocs).catch(() => setDocs([]));
    api.docTypes(lang).then(setDocTypes).catch(() => setDocTypes([]));
  }, [profileId, lang, result]);

  async function send(file: File, hint?: string) {
    if (!profileId) return;
    setBusy(true);
    setError(null);
    try {
      const res = await api.uploadDocument(profileId, lang, file, hint);
      setResult(res);
      setOverride("");
    } catch (err) {
      setError(err instanceof Error ? err.message : t("upload.failed"));
    } finally {
      setBusy(false);
    }
  }

  function onPick(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (file) void send(file);
    e.target.value = "";
  }

  if (!ready) return <Spinner />;

  const doc = result?.document;
  const lowConfidence = doc ? doc.doc_type_confidence < 0.6 || doc.doc_type === "unknown" : false;

  return (
    <div className="space-y-5">
      <header>
        <h1 className="text-2xl font-bold">{t("upload.title")}</h1>
        <p className="text-lg text-ink-soft mt-2">{t("upload.help")}</p>
      </header>

      <input
        ref={fileInput} type="file" accept="image/*,application/pdf"
        capture="environment" onChange={onPick} className="sr-only"
      />
      <button className="btn-primary w-full text-xl" disabled={busy}
        onClick={() => fileInput.current?.click()}>
        <Icon name="camera" className="w-6 h-6" />
        {t("action.take_photo")}
      </button>

      {busy && (
        <div className="card p-5">
          <Spinner label={t("upload.reading")} />
        </div>
      )}

      {error && (
        <div className="card p-4 border-clay-mid/40 bg-clay-light text-clay-deep flex gap-2">
          <Icon name="alert" className="w-5 h-5 shrink-0 mt-1" />
          <p className="text-base">{error}</p>
        </div>
      )}

      {doc && !busy && (
        <section className="card p-5 space-y-4">
          <div className="flex items-start gap-3">
            <span className="w-11 h-11 rounded-full bg-moss-light text-moss-deep grid place-items-center shrink-0">
              <Icon name="check" className="w-6 h-6" />
            </span>
            <div className="min-w-0">
              <h2 className="text-xl font-bold">
                {lowConfidence
                  ? t("upload.detected_unknown")
                  : t("upload.detected", { doc: doc.label })}
              </h2>
              <p className="text-sm text-ink-faint mt-1">
                {doc.ocr_engine} - {Math.round(doc.ocr_confidence * 100)}% -{" "}
                {result?.ocr.line_count} lines
              </p>
            </div>
          </div>

          {lowConfidence && (
            <div className="space-y-2">
              <label className="field-label" htmlFor="override">
                {t("upload.detected_unknown")}
              </label>
              <select id="override" className="input" value={override}
                onChange={(e) => setOverride(e.target.value)}>
                <option value="">--</option>
                {docTypes.map((d) => (
                  <option key={d.doc_type} value={d.doc_type}>{d.label}</option>
                ))}
              </select>
            </div>
          )}

          {doc.number_masked && (
            <p className="text-base bg-sand-deep rounded-xl px-4 py-3">
              <span className="font-semibold">{doc.number_masked}</span>
              <span className="block text-sm text-ink-soft mt-1">{t("upload.privacy")}</span>
            </p>
          )}

          {result && result.changes.length > 0 && (
            <div>
              <h3 className="field-label mb-2">
                {t("upload.found_fields", { n: result.changes.length })}
              </h3>
              <ul className="divide-y divide-sand-line">
                {result.changes.map((c) => (
                  <li key={c.field} className="py-2.5 flex items-center gap-3">
                    <ConfidenceDot value={c.confidence} />
                    <span className="text-base text-ink-soft flex-1 min-w-0">{c.label}</span>
                    <span className="text-base font-semibold text-right break-words max-w-[55%]">
                      {String(c.value)}
                    </span>
                  </li>
                ))}
              </ul>
              <p className="text-sm text-ink-faint mt-2">{t("upload.check_these")}</p>
            </div>
          )}

          {doc.warnings.length > 0 && (
            <p className="text-base text-amber-deep bg-amber-light rounded-xl px-4 py-3">
              {doc.warnings.join(", ")}
            </p>
          )}

          <div className="flex flex-wrap gap-3 pt-1">
            <span className="chip bg-moss-light text-moss-deep">
              {t("schemes.eligible_count", { n: result?.eligible_count ?? 0 })}
            </span>
            {result && result.need_info_count > 0 && (
              <span className="chip bg-amber-light text-amber-deep">
                {t("schemes.need_info_count", { n: result.need_info_count })}
              </span>
            )}
          </div>

          {result && result.next_documents.length > 0 && (
            <p className="text-base bg-indigo-light text-indigo-deep rounded-xl px-4 py-3">
              {t("upload.next_best", {
                doc: result.next_documents[0].label,
                n: result.next_documents[0].unlocks,
              })}
            </p>
          )}

          <div className="flex gap-3">
            <Link href="/schemes" className="btn-primary flex-1">{t("action.continue")}</Link>
            <Link href="/profile" className="btn-secondary flex-1">{t("nav.profile")}</Link>
          </div>
        </section>
      )}

      <section>
        <h2 className="field-label mb-2">{t("nav.vault")}</h2>
        {docs.length === 0 ? (
          <Empty text={t("vault.empty")} />
        ) : (
          <ul className="space-y-2">
            {docs.map((d) => (
              <li key={d.id} className="card px-4 py-3 flex items-center gap-3">
                <Icon name="doc" className="w-5 h-5 text-ink-faint shrink-0" />
                <span className="text-base font-medium flex-1 min-w-0 truncate">{d.label}</span>
                <ConfidenceDot value={d.ocr_confidence} />
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}
