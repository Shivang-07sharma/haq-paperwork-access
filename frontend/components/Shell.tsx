"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useApp } from "@/lib/store";
import { Icon } from "./ui";

const NAV = [
  { href: "/", key: "nav.home", icon: "home" },
  { href: "/upload", key: "nav.upload", icon: "camera" },
  { href: "/profile", key: "nav.profile", icon: "user" },
  { href: "/schemes", key: "nav.schemes", icon: "gift" },
  { href: "/vault", key: "nav.vault", icon: "vault" },
];

/**
 * App frame: a compact header carrying the language switch, and a five-item
 * bottom bar. The bottom bar is deliberately the familiar shape of a phone app
 * rather than a web nav, because that is the pattern this audience already
 * knows from WhatsApp.
 */
export function Shell({ children }: { children: React.ReactNode }) {
  const { t, lang, setLang, languages, error, ready } = useApp();
  const pathname = usePathname();

  return (
    <div className="min-h-screen flex flex-col">
      <header className="sticky top-0 z-20 bg-indigo-deep text-white">
        <div className="mx-auto w-full max-w-2xl px-4 py-3 flex items-center gap-3">
          <Link href="/" className="flex items-baseline gap-2 min-w-0">
            <span className="text-xl font-bold tracking-tight">{t("app.name")}</span>
            <span className="text-sm text-white/70 truncate hidden sm:inline">
              {t("app.tagline")}
            </span>
          </Link>

          <div className="ml-auto flex items-center gap-1" role="group"
            aria-label={t("home.choose_language")}>
            {languages.map((l) => (
              <button
                key={l.code}
                onClick={() => setLang(l.code)}
                aria-pressed={l.code === lang}
                title={l.complete ? l.label : `${l.label} (partial translation)`}
                className={`min-h-[44px] px-3 rounded-lg text-base font-semibold transition-colors ${
                  l.code === lang
                    ? "bg-white text-indigo-deep"
                    : "text-white/85 hover:bg-white/15"
                }`}
              >
                {l.native}
              </button>
            ))}
          </div>
        </div>
      </header>

      {error && (
        <div className="bg-clay-light text-clay-deep border-b border-clay-mid/30">
          <div className="mx-auto w-full max-w-2xl px-4 py-3 flex items-start gap-2 text-base">
            <Icon name="alert" className="w-5 h-5 shrink-0 mt-0.5" />
            <span>{error}</span>
          </div>
        </div>
      )}

      <main className="flex-1 mx-auto w-full max-w-2xl px-4 pb-28 pt-5">
        {ready ? children : null}
      </main>

      <nav className="fixed bottom-0 inset-x-0 z-20 bg-white border-t border-sand-line">
        <div className="mx-auto w-full max-w-2xl grid grid-cols-5">
          {NAV.map((item) => {
            const active =
              item.href === "/" ? pathname === "/" : pathname.startsWith(item.href);
            return (
              <Link
                key={item.href}
                href={item.href}
                aria-current={active ? "page" : undefined}
                className={`flex flex-col items-center justify-center gap-1 py-2 min-h-[64px] text-xs font-semibold ${
                  active ? "text-indigo-deep" : "text-ink-faint"
                }`}
              >
                <Icon name={item.icon} className="w-6 h-6" />
                <span className="leading-tight text-center px-1">{t(item.key)}</span>
                {active && <span className="sr-only">(current)</span>}
              </Link>
            );
          })}
        </div>
      </nav>
    </div>
  );
}
