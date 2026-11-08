/**
 * Typed API client.
 *
 * Responsible for every HTTP call from the browser to the backend: a thin `fetch`
 * wrapper that prefixes NEXT_PUBLIC_API_URL, sends cookies (`credentials: "include"`),
 * and turns the backend's `{ error: { code, message } }` format into a thrown
 * `ApiError`. Request/response types come from `api-types.ts` (generated, don't edit).
 */
import type { components } from "./api-types";

export type Workspace = components["schemas"]["WorkspaceRead"];
export type WorkspaceCreate = components["schemas"]["WorkspaceCreate"];
export type WorkspaceStatus = Workspace["status"];

const BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

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
  const response = await fetch(`${BASE_URL}/api/v1${path}`, {
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

export const api = {
  health: () => request<{ status: string; db: string }>("/health"),
  listWorkspaces: () => request<Workspace[]>("/workspaces"),
  getWorkspace: (id: string) => request<Workspace>(`/workspaces/${id}`),
  createWorkspace: (body: WorkspaceCreate) =>
    request<Workspace>("/workspaces", {
      method: "POST",
      body: JSON.stringify(body),
    }),
  deleteWorkspace: (id: string) =>
    request<void>(`/workspaces/${id}`, { method: "DELETE" }),
};
