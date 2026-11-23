/**
 * Kit entry: inlined by the shell into every v2 app (backend/app/agent/shell.py).
 *
 * 1. Exposes the kit as globals, so app code uses <DataTable/>, records(), fmt… directly.
 * 2. Compiles the app's <script type="text/jsx"> with Sucrase and runs it as an inline
 *    script (the CSP allows inline scripts, not eval), which defines App.
 * 3. Defines render(data), which the shell's bridge calls: it renders <App data/> with
 *    React and throws if rendering failed, so the bridge reports demux:error.
 */
import "./styles.css";
import * as React from "react";
import { flushSync } from "react-dom";
import { createRoot, type Root } from "react-dom/client";
import { transform } from "sucrase";
import {
  FieldList,
  RecordCard,
  RecordSheet,
  RecordSheetProvider,
  useFilters,
  useOpenRecord,
  Value,
} from "./blocks/common";
import { Chart, Dashboard, StatCard, StatRow } from "./blocks/insights";
import { Board, Calendar, DataTable, Gallery, ListDetail, Timeline, ViewTabs } from "./blocks/views";
import {
  aggregate,
  byMonth,
  countBy,
  daysUntil,
  fmt,
  groupBy,
  isEmpty,
  isPast,
  latestThread,
  openEmail,
  records,
  sortBy,
  sumBy,
  toDate,
  tone,
  types,
  uniq,
} from "./lib/data";
import {
  Avatar,
  Badge,
  Button,
  Card,
  Dot,
  EmptyState,
  Grid,
  Input,
  Note,
  OpenEmail,
  Page,
  Progress,
  Row,
  SearchInput,
  Section,
  Select,
  Separator,
  Sheet,
  Stack,
  StatusBadge,
  Tabs,
  Tag,
  Tooltip,
} from "./ui/primitives";

export const KIT = {
  React,
  Fragment: React.Fragment,
  useState: React.useState,
  useMemo: React.useMemo,
  useEffect: React.useEffect,
  useRef: React.useRef,
  useCallback: React.useCallback,
  // data
  records,
  types,
  fmt,
  groupBy,
  aggregate,
  byMonth,
  countBy,
  sumBy,
  sortBy,
  uniq,
  daysUntil,
  isPast,
  toDate,
  isEmpty,
  tone,
  latestThread,
  openEmail,
  // layout and primitives
  Page,
  Section,
  Stack,
  Row,
  Grid,
  Note,
  Separator,
  Button,
  Badge,
  StatusBadge,
  Tag,
  Dot,
  Input,
  SearchInput,
  Select,
  Tabs,
  Sheet,
  Tooltip,
  Avatar,
  Progress,
  Card,
  EmptyState,
  OpenEmail,
  // blocks
  DataTable,
  Board,
  Gallery,
  ListDetail,
  Timeline,
  Calendar,
  ViewTabs,
  StatCard,
  StatRow,
  Chart,
  Dashboard,
  RecordSheet,
  RecordCard,
  FieldList,
  Value,
  useFilters,
  useOpenRecord,
};

const w = window as unknown as Record<string, unknown>;
Object.assign(w, KIT);
w.DemuxKit = KIT;

/* ------------------------------------------------------------------ JSX */

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

if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", compileApps);
else compileApps();

/* ------------------------------------------------------------------ render */

class ErrorBoundary extends React.Component<
  { resetKey: number; children: React.ReactNode },
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
    if (this.state.error)
      return (
        <div className="rounded-card bg-danger-bg px-4 py-3 text-sm text-danger">
          This workspace hit a display error.
        </div>
      );
    return this.props.children;
  }
}

declare const App: unknown;

let root: Root | null = null;
let lastError: unknown = null;
let renders = 0;

function render(data: unknown): void {
  const app =
    typeof App !== "undefined" ? App : (w.App as unknown);
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
      <ErrorBoundary resetKey={renders}>
        <RecordSheetProvider>
          <Component data={data ?? {}} />
        </RecordSheetProvider>
      </ErrorBoundary>,
    ),
  );
  if (lastError) throw lastError instanceof Error ? lastError : new Error(String(lastError));
}

w.render = render;
