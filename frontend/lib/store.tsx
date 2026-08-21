"use client";

/**
 * Session context: language, translated strings, and the profile id.
 *
 * Strings come from the backend rather than a bundled locale file, so the
 * server stays the single source of truth for wording and a translation fix
 * does not need a frontend release.
 */

import {
  createContext, useCallback, useContext, useEffect, useMemo, useState,
} from "react";
import {
  Language, api, ensureProfile, getStoredLang, setStoredLang,
} from "./api";

interface AppState {
  lang: string;
  setLang: (lang: string) => void;
  languages: Language[];
  strings: Record<string, string>;
  t: (key: string, args?: Record<string, string | number>) => string;
  ttsLocale: string;
  profileId: number | null;
  ready: boolean;
  error: string | null;
  version: number;
  refresh: () => void;
}

const Ctx = createContext<AppState | null>(null);

function interpolate(template: string, args?: Record<string, string | number>) {
  if (!args) return template;
  return template.replace(/\{(\w+)\}/g, (whole, key) =>
    key in args ? String(args[key]) : whole,
  );
}

export function AppProvider({ children }: { children: React.ReactNode }) {
  const [lang, setLangState] = useState("en");
  const [languages, setLanguages] = useState<Language[]>([]);
  const [strings, setStrings] = useState<Record<string, string>>({});
  const [profileId, setProfileId] = useState<number | null>(null);
  const [ready, setReady] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [version, setVersion] = useState(0);

  // First paint reads the stored language so a returning user is not flashed
  // English before their choice loads.
  useEffect(() => {
    setLangState(getStoredLang());
  }, []);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const [langs, bundle, id] = await Promise.all([
          api.languages(),
          api.strings(lang),
          ensureProfile(lang),
        ]);
        if (cancelled) return;
        setLanguages(langs);
        setStrings(bundle);
        setProfileId(id);
        setError(null);
      } catch (err) {
        if (!cancelled) {
          setError(
            err instanceof Error
              ? `Cannot reach the server. Is the backend running on port 8000? (${err.message})`
              : "Cannot reach the server.",
          );
        }
      } finally {
        if (!cancelled) setReady(true);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [lang]);

  const setLang = useCallback((next: string) => {
    setStoredLang(next);
    setLangState(next);
  }, []);

  const t = useCallback(
    (key: string, args?: Record<string, string | number>) =>
      interpolate(strings[key] ?? key, args),
    [strings],
  );

  const ttsLocale = useMemo(
    () => languages.find((l) => l.code === lang)?.tts ?? "en-IN",
    [languages, lang],
  );

  const value: AppState = {
    lang, setLang, languages, strings, t, ttsLocale, profileId, ready, error, version,
    refresh: () => setVersion((v) => v + 1),
  };

  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useApp(): AppState {
  const ctx = useContext(Ctx);
  if (!ctx) throw new Error("useApp must be used inside AppProvider");
  return ctx;
}
