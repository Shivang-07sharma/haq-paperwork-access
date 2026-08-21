"use client";

import Link from "next/link";
import { SchemeExplanation } from "@/lib/api";
import { useApp } from "@/lib/store";
import { Icon, StatusPill } from "./ui";

// Insurance and health schemes quote a maximum cover, not money received. The
// label has to say so, or a Rs 5 lakh hospital cover reads as a Rs 5 lakh payout.
const COVER_CATEGORIES = new Set(["health", "insurance"]);

function periodSuffix(
  scheme: SchemeExplanation,
  t: (key: string) => string,
): string {
  if (COVER_CATEGORIES.has(scheme.category)) return t("schemes.cover_suffix");
  if (scheme.benefit_period === "month") return t("schemes.per_month");
  if (scheme.benefit_period === "year") return t("schemes.per_year");
  return "";
}

const EDGE: Record<string, string> = {
  eligible: "border-l-moss-mid",
  need_more_info: "border-l-amber-mid",
  not_eligible: "border-l-sand-line",
};

export function SchemeCard({ scheme }: { scheme: SchemeExplanation }) {
  const { t } = useApp();
  const dim = scheme.status === "not_eligible";

  return (
    <Link
      href={`/schemes/${scheme.scheme_id}`}
      className={`card border-l-[6px] ${EDGE[scheme.status]} block p-4 hover:border-indigo-mid transition-colors ${
        dim ? "opacity-65" : ""
      }`}
    >
      <div className="flex items-start gap-3">
        <div className="min-w-0 flex-1">
          <h3 className="text-lg font-bold leading-snug">{scheme.name}</h3>
          <p className="text-base text-ink-soft mt-1 line-clamp-2">{scheme.what_you_get}</p>
        </div>
        <Icon name="arrow" className="w-5 h-5 text-ink-faint shrink-0 mt-1" />
      </div>

      <div className="flex flex-wrap items-center gap-2 mt-3">
        <StatusPill status={scheme.status} label={scheme.status_short} />

        {scheme.status === "eligible" && scheme.benefit_amount ? (
          <span className="chip bg-indigo-light text-indigo-deep">
            {scheme.benefit_amount_text} {periodSuffix(scheme, t)}
          </span>
        ) : null}

        {scheme.status === "need_more_info" && scheme.still_needed.length > 0 ? (
          <span className="text-sm text-amber-deep font-medium">
            {scheme.still_needed[0].field_label}
          </span>
        ) : null}

        {scheme.application ? (
          <span className="chip bg-sand-deep text-ink-soft ml-auto">
            {scheme.application.status_label}
          </span>
        ) : null}
      </div>
    </Link>
  );
}
