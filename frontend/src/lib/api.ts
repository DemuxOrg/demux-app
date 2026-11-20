/**
 * Typed API client.
 *
 * Responsible for every HTTP call from the browser to the backend: a thin `fetch`
 * wrapper that prefixes NEXT_PUBLIC_API_URL, sends the better-auth session cookie
 * (`credentials: "include"`; the backend resolves it), and turns the backend's `{ error: { code, message } }`
 * format into a thrown `ApiError`. Types come from `api-types.ts` (generated).
 */
import type { components } from "./api-types";

type S = components["schemas"];
export type Me = S["Me"];
export type MeUpdate = S["MeUpdate"];
export type WorkspaceSummary = S["WorkspaceSummary"];
export type WorkspaceDetail = S["WorkspaceDetail"];
export type WorkspaceStatus = WorkspaceSummary["status"];
export type RunRead = S["RunRead"];
export type RunEvent = S["RunEvent"];
export type ChangeRead = S["ChangeRead"];
export type AppDoc = S["AppDoc"];
export type DataDoc = S["DataDoc"];
export type GuideDoc = S["GuideDoc"];

export const API_URL =
  process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
/** Starts the backend-owned Gmail OAuth flow (a full-page navigation, not fetch). */
export const CONNECT_GMAIL_URL = `${API_URL}/api/v1/auth/google/login`;

export class ApiError extends Error {
  constructor(
    public status: number,
    public code: string,
    message: string,
  ) {
    super(message);
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_URL}/api/v1${path}`, {
    ...init,
    credentials: "include",
    headers: { "Content-Type": "application/json", ...init?.headers },
    cache: "no-store",
  });
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    throw new ApiError(
      response.status,
      body?.error?.code ?? "unknown_error",
      body?.error?.message ?? response.statusText,
    );
  }
  return response.status === 204 ? (undefined as T) : response.json();
}

const post = <T>(path: string, body?: unknown) =>
  request<T>(path, {
    method: "POST",
    body: body === undefined ? undefined : JSON.stringify(body),
  });

export const api = {
  health: () => request<{ status: string; db: string }>("/health"),
  me: () => request<Me>("/me"),
  updateMe: (body: MeUpdate) =>
    request<Me>("/me", { method: "PATCH", body: JSON.stringify(body) }),
  disconnectGmail: () => request<Me>("/me/gmail", { method: "DELETE" }),
  appShell: () => request<{ head: string }>("/app-shell"),
  listWorkspaces: () => request<WorkspaceSummary[]>("/workspaces"),
  createWorkspace: (prompt: string) =>
    post<WorkspaceSummary>("/workspaces", { prompt }),
  getWorkspace: (id: string) => request<WorkspaceDetail>(`/workspaces/${id}`),
  renameWorkspace: (id: string, name: string) =>
    request<WorkspaceSummary>(`/workspaces/${id}`, {
      method: "PATCH",
      body: JSON.stringify({ name }),
    }),
  deleteWorkspace: (id: string) =>
    request<void>(`/workspaces/${id}`, { method: "DELETE" }),
  getApp: (id: string) => request<AppDoc>(`/workspaces/${id}/app`),
  getData: (id: string) => request<DataDoc>(`/workspaces/${id}/data`),
  getGuide: (id: string) => request<GuideDoc>(`/workspaces/${id}/guide`),
  listChanges: (id: string, limit = 100) =>
    request<ChangeRead[]>(`/workspaces/${id}/changes?limit=${limit}`),
  listRuns: (id: string, limit = 30) =>
    request<RunRead[]>(`/workspaces/${id}/runs?limit=${limit}`),
  sendMessage: (id: string, text: string) =>
    post<{ run_id: string }>(`/workspaces/${id}/messages`, { text }),
  syncNow: (id: string) => post<{ run_id: string }>(`/workspaces/${id}/sync`),
  undo: (id: string) => post<DataDoc>(`/workspaces/${id}/undo`),
  rebuild: (id: string) => post<WorkspaceSummary>(`/workspaces/${id}/rebuild`),
};

/** Send the user to sign in when the session is missing or expired. */
export function handleAuthError(e: unknown): boolean {
  if (e instanceof ApiError && e.status === 401) {
    window.location.href = "/login";
    return true;
  }
  return false;
}

export function timeAgo(iso: string | null | undefined): string {
  if (!iso) return "not yet";
  const s = Math.max(0, (Date.now() - new Date(iso).getTime()) / 1000);
  if (s < 60) return "just now";
  if (s < 3600) return `${Math.floor(s / 60)} min ago`;
  if (s < 86400) return `${Math.floor(s / 3600)} h ago`;
  return `${Math.floor(s / 86400)} d ago`;
}

export function countLabel(counts: Record<string, number>): string {
  const parts = Object.entries(counts)
    .filter(([t]) => !t.startsWith("_"))
    .map(([t, n]) => {
      const noun = t.replace(/_/g, " ");
      return `${n} ${n === 1 || noun.endsWith("s") ? noun : `${noun}s`}`;
    });
  return parts.length ? parts.join(" · ") : "No records yet";
}
