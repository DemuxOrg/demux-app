/**
 * The prompt of a cancelled build, handed to the Create page (theme.md §7.10) so the
 * user can reword it. A tiny external store (`useDraftPrompt`): the Create page stays
 * mounted while hidden, so it must react when a draft arrives. Mirrored in
 * sessionStorage so a reload keeps it; never in the URL (a prompt can be personal, and
 * URLs end up in history and logs).
 */
import { useSyncExternalStore } from "react";

const KEY = "demux.draftPrompt";
const listeners = new Set<() => void>();

function read(): string {
  try {
    return sessionStorage.getItem(KEY) ?? "";
  } catch {
    return "";
  }
}

function write(prompt: string) {
  try {
    if (prompt) sessionStorage.setItem(KEY, prompt);
    else sessionStorage.removeItem(KEY);
  } catch {
    /* storage unavailable: Create just opens empty */
  }
  listeners.forEach((l) => l());
}

export const saveDraftPrompt = (prompt: string) => write(prompt);
export const clearDraftPrompt = () => write("");

function subscribe(listener: () => void) {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

/** The waiting draft ("" when none). */
export function useDraftPrompt(): string {
  return useSyncExternalStore(subscribe, read, () => "");
}
