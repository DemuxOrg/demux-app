/**
 * The runtime both app bundles install (the kit, index.tsx, and the studio, studio.tsx).
 *
 * 1. Compiles the app's <script type="text/jsx"> with Sucrase and runs it as an inline
 *    script (the CSP allows inline scripts, not eval), which defines App.
 * 2. Defines render(data), which the shell's bridge calls: it renders <App data/> with
 *    React and throws if rendering failed, so the bridge reports demux:error.
 */
import * as React from "react";
import { flushSync } from "react-dom";
import { createRoot, type Root } from "react-dom/client";
import { transform } from "sucrase";
import { CHANGES_CSS, noteData } from "./lib/changes";

function compileApps(): void {
  const scripts = Array.from(document.querySelectorAll('script[type="text/jsx"]'));
  for (const s of scripts) {
    let code: string;
    try {
      code = transform(s.textContent ?? "", {
        transforms: ["jsx", "typescript"],
        production: true,
        jsxPragma: "React.createElement",
        jsxFragmentPragma: "React.Fragment",
      }).code;
    } catch (e) {
      throw new Error(`The app's JSX does not compile: ${(e as Error).message}`);
    }
    const el = document.createElement("script");
    el.textContent = code;
    s.after(el);
  }
}

class ErrorBoundary extends React.Component<
  { resetKey: number; fallback: React.ReactNode; children: React.ReactNode },
  { error: Error | null; key: number }
> {
  state = { error: null as Error | null, key: this.props.resetKey };
  static getDerivedStateFromError(error: Error) {
    return { error };
  }
  static getDerivedStateFromProps(props: { resetKey: number }, state: { key: number }) {
    return props.resetKey !== state.key ? { error: null, key: props.resetKey } : null;
  }
  render() {
    return this.state.error ? this.props.fallback : this.props.children;
  }
}

declare const App: unknown;

export function installRuntime({
  fallback,
  wrap = (app) => app,
}: {
  /** Shown in place of the app when it throws while rendering. */
  fallback: React.ReactNode;
  /** Providers around the app. */
  wrap?: (app: React.ReactNode) => React.ReactNode;
}): void {
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", compileApps);
  else compileApps();

  const w = window as unknown as Record<string, unknown>;
  let root: Root | null = null;
  let lastError: unknown = null;
  let renders = 0;
  let expiry: ReturnType<typeof setTimeout> | undefined;

  const style = document.createElement("style");
  style.textContent = CHANGES_CSS;
  document.head.appendChild(style);

  function render(data: unknown): void {
    // The keys the page just changed (bridge: `demux:data` … `changed`), consumed once.
    const changed = w.__demuxChanged;
    w.__demuxChanged = undefined;
    const hold = noteData(data, changed);
    clearTimeout(expiry);
    if (hold > 0)
      expiry = setTimeout(() => {
        try {
          render(data); // the marks expired: render without them
        } catch {
          /* the next data message renders again */
        }
      }, hold + 20);
    const app = typeof App !== "undefined" ? App : (w.App as unknown);
    if (typeof app !== "function") throw new Error("The app must define function App({ data })");
    let el = document.getElementById("demux-root");
    if (!el) {
      el = document.createElement("div");
      el.id = "demux-root";
      document.body.appendChild(el);
    }
    root ??= createRoot(el, {
      onUncaughtError: (e) => {
        lastError = e;
      },
      onCaughtError: (e) => {
        lastError = e;
      },
    });
    lastError = null;
    renders += 1;
    const Component = app as React.ComponentType<{ data: unknown }>;
    flushSync(() =>
      root!.render(
        <ErrorBoundary resetKey={renders} fallback={fallback}>
          {wrap(<Component data={data ?? {}} />)}
        </ErrorBoundary>,
      ),
    );
    if (lastError) throw lastError instanceof Error ? lastError : new Error(String(lastError));
  }

  w.render = render;
}
