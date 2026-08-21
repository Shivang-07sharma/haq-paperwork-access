"use client";

import { useEffect, useState } from "react";
import { SchemeStatus } from "@/lib/api";
import { useApp } from "@/lib/store";

/* ----------------------------------------------------------------- icons */

const PATHS: Record<string, string> = {
  home: "M3 10.5 12 3l9 7.5V21a1 1 0 0 1-1 1h-5v-7H9v7H4a1 1 0 0 1-1-1z",
  doc: "M6 2h8l4 4v16H6zM14 2v4h4",
  user: "M12 12a4 4 0 1 0 0-8 4 4 0 0 0 0 8zM4 21a8 8 0 0 1 16 0",
  gift: "M3 11h18v10H3zM3 7h18v4H3zM12 7v14M12 7C9 7 7 3 9.5 3S12 7 12 7zM12 7c3 0 5-4 2.5-4S12 7 12 7z",
  vault: "M4 4h16v16H4zM12 9a3 3 0 1 0 0 6 3 3 0 0 0 0-6zM12 6v1M12 17v1",
  check: "m4 12 5 5L20 6",
  cross: "M6 6l12 12M18 6 6 18",
  question: "M9 9a3 3 0 1 1 4 2.8c-.7.3-1 .9-1 1.7v.5M12 17.5v.5",
  sound: "M4 9h4l5-4v14l-5-4H4zM16.5 8.5a5 5 0 0 1 0 7M19 6a8.5 8.5 0 0 1 0 12",
  stop: "M6 6h12v12H6z",
  clock: "M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18zM12 7v5l3 2",
  alert: "M12 3 2 20h20zM12 10v4M12 17.5v.5",
  camera: "M3 8h4l2-2h6l2 2h4v12H3zM12 17a4 4 0 1 0 0-8 4 4 0 0 0 0 8z",
  arrow: "m9 6 6 6-6 6",
  download: "M12 4v11m0 0 4-4m-4 4-4-4M4 20h16",
};

export function Icon({ name, className = "w-6 h-6" }: { name: string; className?: string }) {
  return (
    <svg
      viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}
      strokeLinecap="round" strokeLinejoin="round" className={className} aria-hidden="true"
    >
      <path d={PATHS[name] ?? PATHS.doc} />
    </svg>
  );
}

/* ---------------------------------------------------------------- status */

const STATUS_STYLE: Record<SchemeStatus, string> = {
  eligible: "bg-moss-light text-moss-deep",
  need_more_info: "bg-amber-light text-amber-deep",
  not_eligible: "bg-sand-deep text-ink-faint",
};

const STATUS_ICON: Record<SchemeStatus, string> = {
  eligible: "check",
  need_more_info: "question",
  not_eligible: "cross",
};

export function StatusPill({ status, label }: { status: SchemeStatus; label: string }) {
  return (
    <span className={`chip ${STATUS_STYLE[status]}`}>
      <Icon name={STATUS_ICON[status]} className="w-4 h-4" />
      {label}
    </span>
  );
}

/* ------------------------------------------------------------ speak text */

/**
 * Reads a block of text aloud in the active language.
 *
 * This is the single most useful affordance in the app for somebody who cannot
 * read comfortably, and it costs nothing: the browser speech engine is already
 * on the device. If no voice for the language exists the button hides rather
 * than reading Hindi text in an English accent.
 */
export function SpeakButton({ text, className = "" }: { text: string; className?: string }) {
  const { ttsLocale, t } = useApp();
  const [speaking, setSpeaking] = useState(false);
  const [supported, setSupported] = useState(false);

  useEffect(() => {
    if (typeof window === "undefined" || !window.speechSynthesis) return;
    const check = () => {
      const voices = window.speechSynthesis.getVoices();
      const base = ttsLocale.split("-")[0];
      setSupported(voices.some((v) => v.lang.toLowerCase().startsWith(base)));
    };
    check();
    window.speechSynthesis.addEventListener("voiceschanged", check);
    return () => window.speechSynthesis.removeEventListener("voiceschanged", check);
  }, [ttsLocale]);

  useEffect(() => () => window.speechSynthesis?.cancel(), []);

  if (!supported || !text) return null;

  const speak = () => {
    const synth = window.speechSynthesis;
    if (speaking) {
      synth.cancel();
      setSpeaking(false);
      return;
    }
    synth.cancel();
    const utterance = new SpeechSynthesisUtterance(text);
    utterance.lang = ttsLocale;
    const base = ttsLocale.split("-")[0];
    const voice = synth.getVoices().find((v) => v.lang.toLowerCase().startsWith(base));
    if (voice) utterance.voice = voice;
    utterance.rate = 0.92;
    utterance.onend = () => setSpeaking(false);
    utterance.onerror = () => setSpeaking(false);
    setSpeaking(true);
    synth.speak(utterance);
  };

  return (
    <button type="button" onClick={speak} className={`btn-quiet ${className}`}
      aria-label={speaking ? t("action.stop") : t("action.listen")}>
      <Icon name={speaking ? "stop" : "sound"} className="w-5 h-5" />
      {speaking ? t("action.stop") : t("action.listen")}
    </button>
  );
}

/* ----------------------------------------------------------------- misc */

export function Progress({ percent, tone = "indigo" }: { percent: number; tone?: string }) {
  const bar = tone === "moss" ? "bg-moss-mid" : "bg-indigo-mid";
  return (
    <div className="h-2.5 w-full rounded-full bg-sand-deep overflow-hidden"
      role="progressbar" aria-valuenow={Math.round(percent)} aria-valuemin={0} aria-valuemax={100}>
      <div className={`h-full rounded-full ${bar}`} style={{ width: `${Math.min(100, Math.max(0, percent))}%` }} />
    </div>
  );
}

export function Spinner({ label }: { label?: string }) {
  return (
    <div className="flex items-center gap-3 text-ink-soft py-8">
      <span className="inline-block w-6 h-6 rounded-full border-[3px] border-sand-line border-t-indigo-mid animate-spin" />
      {label && <span className="text-lg">{label}</span>}
    </div>
  );
}

export function ConfidenceDot({ value }: { value: number }) {
  const tone = value >= 0.85 ? "bg-moss-mid" : value >= 0.6 ? "bg-amber-mid" : "bg-clay-mid";
  return <span className={`inline-block w-2.5 h-2.5 rounded-full ${tone}`} title={`confidence ${Math.round(value * 100)}%`} />;
}

export function Empty({ text }: { text: string }) {
  return <p className="text-lg text-ink-soft py-10 text-center">{text}</p>;
}
