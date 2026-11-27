/**
 * Kit entry: inlined by the shell into every v2 app (backend/app/agent/shell.py).
 *
 * 1. Exposes the kit as globals, so app code uses <DataTable/>, records(), fmt… directly.
 * 2. Installs the runtime shared with the studio runtime (runtime.tsx): compiles the
 *    app's JSX and defines render(data) for the shell's bridge.
 */
import "./styles.css";
import * as React from "react";
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
import { installRuntime } from "./runtime";
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

/* ------------------------------------------------------------------ runtime */

installRuntime({
  fallback: (
    <div className="rounded-card bg-danger-bg px-4 py-3 text-sm text-danger">
      This workspace hit a display error.
    </div>
  ),
  wrap: (app) => <RecordSheetProvider>{app}</RecordSheetProvider>,
});
