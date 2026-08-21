/**
 * Typed client for the Haq backend.
 *
 * Every call takes the active language, because the backend does the
 * translating -- the UI never holds a second copy of the scheme wording. The
 * profile id lives in localStorage so a demo survives a page reload without a
 * login screen standing between a person and their documents.
 */

const BASE = process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000";
const PROFILE_KEY = "haq.profile_id";
const LANG_KEY = "haq.lang";

export interface Language {
  code: string;
  label: string;
  native: string;
  tts: string;
  coverage: number;
  complete: boolean;
}

export interface FieldSpec {
  name: string;
  type: "text" | "date" | "number" | "tel" | "choice" | "boolean";
  group: string;
  label: string;
  unit?: string;
  options?: string[];
  option_labels?: Record<string, string>;
}

export interface FieldSource {
  value: unknown;
  method: "ocr" | "manual";
  confidence: number;
  doc_type: string | null;
  source_document_id: number | null;
  at: string;
}

export interface ProfileDto {
  id: number;
  language: string;
  fields: Record<string, unknown>;
  derived: { age: number | null; is_bpl: boolean | null };
  aadhaar_last4: string | null;
  account_last4: string | null;
  field_sources: Record<string, FieldSource>;
  filled_count: number;
  total_count: number;
  completeness: number;
}

export interface DocumentDto {
  id: number;
  doc_type: string;
  label: string;
  doc_type_confidence: number;
  original_filename: string;
  mime_type: string;
  size_bytes: number;
  ocr_engine: string | null;
  ocr_confidence: number;
  extracted_fields: Record<
    string,
    { value: unknown; confidence: number; raw: string | null; note: string | null }
  >;
  warnings: string[];
  number_masked: string | null;
  issue_date: string | null;
  expiry_date: string | null;
  uploaded_at: string | null;
  state: "valid" | "expiring_soon" | "expired" | "no_expiry";
  days_left: number | null;
}

export interface UploadResult {
  document: DocumentDto;
  changes: { field: string; label: string; value: unknown; confidence: number; replaced: boolean }[];
  ocr: { engine: string; confidence: number; line_count: number; warnings: string[] };
  profile: ProfileDto;
  eligible_count: number;
  need_info_count: number;
  next_documents: { doc_type: string; label: string; unlocks: number; scheme_ids: string[] }[];
}

export type SchemeStatus = "eligible" | "need_more_info" | "not_eligible";

export interface Reason {
  text: string;
  field: string;
}

export interface NeededItem extends Reason {
  field_label: string;
  document_hints: string[];
}

export interface SchemeExplanation {
  scheme_id: string;
  name: string;
  full_name: string;
  department: string;
  category: string;
  icon: string;
  status: SchemeStatus;
  status_label: string;
  status_short: string;
  confidence: number;
  score: number;
  headings: Record<string, string>;
  what_it_is: string;
  what_you_get: string;
  benefit_amount: number | null;
  benefit_amount_text: string;
  benefit_period: string;
  why_you_qualify: Reason[];
  why_not: Reason[];
  still_needed: NeededItem[];
  assumptions: Reason[];
  what_to_do: string[];
  documents_needed: { doc_type: string; label: string; have: boolean }[];
  where_to_go: string;
  apply_url: string;
  processing_time: string;
  missing_fields: string[];
  documents_that_would_help: { doc_type: string; label: string }[];
  speech_text: string;
  application?: ApplicationDto | null;
  form_preview?: {
    form_id: string;
    title: string;
    completion_percent: number;
    missing_required: { field: string; label: string }[];
    field_count: number;
  };
}

export interface SchemesResponse {
  schemes: SchemeExplanation[];
  summary: {
    eligible: number;
    need_more_info: number;
    not_eligible: number;
    annual_value: number;
    annual_value_text: string;
    cover_value: number;
    cover_value_text: string;
  };
  next_documents: { doc_type: string; label: string; unlocks: number; scheme_ids: string[] }[];
  disclaimer: string;
}

export interface ApplicationDto {
  id: number;
  scheme_id: string;
  scheme_name: string;
  status: string;
  status_label: string;
  reference_no: string | null;
  completion_percent: number;
  missing_fields: { field: string; label: string }[];
  has_form: boolean;
  days_waiting: number | null;
  created_at: string | null;
  updated_at: string | null;
  events: { status: string; status_label: string; note: string | null; actor: string; at: string | null }[];
}

export interface VaultResponse {
  documents: DocumentDto[];
  reminders: {
    id: number;
    kind: string;
    text: string;
    due_date: string | null;
    document_id: number | null;
    application_id: number | null;
  }[];
  counts: { total: number; expiring_soon: number; expired: number };
}

export interface QuestionDto extends FieldSpec {
  unlocks: number;
  scheme_ids: string[];
}

class ApiError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.status = status;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const isForm = init?.body instanceof FormData;
  const res = await fetch(`${BASE}${path}`, {
    ...init,
    headers: {
      ...(isForm ? {} : { "Content-Type": "application/json" }),
      ...(init?.headers || {}),
    },
    cache: "no-store",
  });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = body?.detail ?? detail;
    } catch {
      /* body was not JSON; the status text is the best we have */
    }
    throw new ApiError(String(detail), res.status);
  }
  return (await res.json()) as T;
}

/* -------------------------------------------------------------- session */

export function getStoredLang(): string {
  if (typeof window === "undefined") return "en";
  return window.localStorage.getItem(LANG_KEY) || "en";
}

export function setStoredLang(lang: string) {
  window.localStorage.setItem(LANG_KEY, lang);
}

export function getStoredProfileId(): number | null {
  if (typeof window === "undefined") return null;
  const raw = window.localStorage.getItem(PROFILE_KEY);
  return raw ? Number(raw) : null;
}

export function setStoredProfileId(id: number) {
  window.localStorage.setItem(PROFILE_KEY, String(id));
}

export function clearSession() {
  window.localStorage.removeItem(PROFILE_KEY);
  window.localStorage.removeItem(LANG_KEY);
}

/** Return the existing profile id, creating one on first visit. */
export async function ensureProfile(lang: string): Promise<number> {
  const existing = getStoredProfileId();
  if (existing) {
    try {
      await request<ProfileDto>(`/api/profiles/${existing}?lang=${lang}`);
      return existing;
    } catch {
      // The database was reset under us; start a fresh profile rather than
      // leaving the app wedged on a dead id.
    }
  }
  const created = await request<ProfileDto>("/api/profiles", {
    method: "POST",
    body: JSON.stringify({ language: lang }),
  });
  setStoredProfileId(created.id);
  return created.id;
}

/* ----------------------------------------------------------------- api */

export const api = {
  health: () =>
    request<{ status: string; schemes: number; ocr_providers: Record<string, boolean> }>(
      "/api/health",
    ),

  languages: () => request<Language[]>("/api/meta/languages"),
  strings: (lang: string) => request<Record<string, string>>(`/api/meta/strings?lang=${lang}`),
  docTypes: (lang: string) =>
    request<{ doc_type: string; label: string }[]>(`/api/meta/doc-types?lang=${lang}`),
  fields: (lang: string) => request<FieldSpec[]>(`/api/meta/fields?lang=${lang}`),

  profile: (id: number, lang: string) => request<ProfileDto>(`/api/profiles/${id}?lang=${lang}`),
  updateProfile: (id: number, lang: string, patch: Record<string, unknown>) =>
    request<ProfileDto>(`/api/profiles/${id}?lang=${lang}`, {
      method: "PATCH",
      body: JSON.stringify(patch),
    }),
  questions: (id: number, lang: string) =>
    request<QuestionDto[]>(`/api/profiles/${id}/questions?lang=${lang}`),

  documents: (id: number, lang: string) =>
    request<DocumentDto[]>(`/api/profiles/${id}/documents?lang=${lang}`),
  uploadDocument: (id: number, lang: string, file: File, docType?: string) => {
    const body = new FormData();
    body.append("file", file);
    if (docType) body.append("doc_type", docType);
    return request<UploadResult>(`/api/profiles/${id}/documents?lang=${lang}`, {
      method: "POST",
      body,
    });
  },
  deleteDocument: (docId: number) =>
    request<{ deleted: number }>(`/api/documents/${docId}`, { method: "DELETE" }),
  documentFileUrl: (docId: number) => `${BASE}/api/documents/${docId}/file`,

  schemes: (id: number, lang: string) => request<SchemesResponse>(`/api/profiles/${id}/schemes?lang=${lang}`),
  scheme: (id: number, schemeId: string, lang: string) =>
    request<SchemeExplanation>(`/api/profiles/${id}/schemes/${schemeId}?lang=${lang}`),

  applications: (id: number, lang: string) =>
    request<ApplicationDto[]>(`/api/profiles/${id}/applications?lang=${lang}`),
  createApplication: (id: number, lang: string, schemeId: string) =>
    request<ApplicationDto>(`/api/profiles/${id}/applications?lang=${lang}`, {
      method: "POST",
      body: JSON.stringify({ scheme_id: schemeId }),
    }),
  setApplicationStatus: (appId: number, lang: string, status: string, note?: string) =>
    request<ApplicationDto>(`/api/applications/${appId}/status?lang=${lang}`, {
      method: "POST",
      body: JSON.stringify({ status, note }),
    }),
  applicationFormUrl: (appId: number) => `${BASE}/api/applications/${appId}/form`,

  vault: (id: number, lang: string) => request<VaultResponse>(`/api/profiles/${id}/vault?lang=${lang}`),
  completeReminder: (reminderId: number) =>
    request<{ id: number; done: boolean }>(`/api/reminders/${reminderId}/done`, { method: "POST" }),
};

export { ApiError, BASE };
