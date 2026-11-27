/**
 * Studio runtime (v3): inlined by the shell into every app the UI model designs
 * (backend/app/agent/shell.py, docs/UI_GENERATION_PLAN.md §11). Unlike the kit (v2) it
 * brings no components and no look, only libraries, as globals: the iframe has no
 * network and the app cannot import anything. The app decides its own layout, colours
 * and type; Tailwind's browser build (inlined next to this bundle) styles its classes.
 *
 * Globals: React and its hooks, `cx` (class names), Recharts (the namespace and the
 * common chart parts), `Icon` (a curated lucide set by name), and the data helpers
 * `records`, `types`, `openEmail`. Every one is documented in studio.md, the UI model's
 * reference (the build checks it).
 */
import { clsx } from "clsx";
import {
  Activity,
  AlarmClock,
  Archive,
  ArrowDown,
  ArrowDownRight,
  ArrowLeft,
  ArrowRight,
  ArrowUp,
  ArrowUpRight,
  AtSign,
  Award,
  Baby,
  Banknote,
  Bed,
  Bell,
  Book,
  Bookmark,
  BookOpen,
  Box,
  Briefcase,
  Building2,
  Bus,
  Calendar,
  CalendarCheck,
  CalendarClock,
  CalendarDays,
  Car,
  ChartBar,
  ChartLine,
  ChartPie,
  Check,
  CheckCheck,
  ChevronDown,
  ChevronLeft,
  ChevronRight,
  ChevronsUpDown,
  ChevronUp,
  CircleAlert,
  CircleCheck,
  CircleDashed,
  CircleDot,
  CircleX,
  Clipboard,
  ClipboardList,
  Clock,
  Cloud,
  Code,
  Coffee,
  Coins,
  Compass,
  Copy,
  CreditCard,
  Database,
  DollarSign,
  Dumbbell,
  Ellipsis,
  Euro,
  ExternalLink,
  Eye,
  EyeOff,
  File,
  FileText,
  Film,
  Filter,
  Flag,
  Flame,
  Folder,
  Gift,
  Globe,
  GraduationCap,
  Hash,
  Heart,
  HeartPulse,
  History,
  Hotel,
  Hourglass,
  House,
  Image,
  Inbox,
  Info,
  Key,
  Landmark,
  Laptop,
  Layers,
  LayoutDashboard,
  LayoutGrid,
  LayoutList,
  Leaf,
  Link,
  List,
  ListChecks,
  ListTodo,
  LoaderCircle,
  Lock,
  Mail,
  MailOpen,
  Map,
  MapPin,
  Maximize2,
  Menu,
  MessageSquare,
  Minus,
  Monitor,
  Moon,
  Music,
  Package,
  PackageCheck,
  Paperclip,
  Pencil,
  Percent,
  Phone,
  PiggyBank,
  Pill,
  Pin,
  Plane,
  Plus,
  Receipt,
  RefreshCw,
  Repeat,
  Rocket,
  RotateCcw,
  Scale,
  Search,
  Send,
  Settings,
  Share2,
  Shield,
  ShieldCheck,
  Ship,
  Shirt,
  ShoppingBag,
  ShoppingCart,
  Sigma,
  SlidersHorizontal,
  Smartphone,
  Sparkles,
  SquareKanban,
  Star,
  Stethoscope,
  Store,
  Sun,
  Table,
  Tag,
  Target,
  Ticket,
  Timer,
  Train,
  TrendingDown,
  TrendingUp,
  TriangleAlert,
  Trophy,
  Truck,
  User,
  UserCheck,
  Users,
  Utensils,
  Wallet,
  Wrench,
  X,
  Zap,
  type LucideIcon,
} from "lucide-react";
import * as React from "react";
import * as Recharts from "recharts";
import { openEmail, records, types } from "./lib/data";
import { installRuntime } from "./runtime";

// ICONS-START (scripts/finish.mjs lists these names in studio.md)
const ICON_SET: Record<string, LucideIcon> = {
  Activity, AlarmClock, Archive, ArrowDown, ArrowDownRight, ArrowLeft, ArrowRight, ArrowUp,
  ArrowUpRight, AtSign, Award, Baby, Banknote, Bed, Bell, Book, Bookmark, BookOpen, Box,
  Briefcase, Building2, Bus, Calendar, CalendarCheck, CalendarClock, CalendarDays, Car,
  ChartBar, ChartLine, ChartPie, Check, CheckCheck, ChevronDown, ChevronLeft, ChevronRight,
  ChevronsUpDown, ChevronUp, CircleAlert, CircleCheck, CircleDashed, CircleDot, CircleX,
  Clipboard, ClipboardList, Clock, Cloud, Code, Coffee, Coins, Compass, Copy, CreditCard,
  Database, DollarSign, Dumbbell, Ellipsis, Euro, ExternalLink, Eye, EyeOff, File, FileText,
  Film, Filter, Flag, Flame, Folder, Gift, Globe, GraduationCap, Hash, Heart, HeartPulse,
  History, Hotel, Hourglass, House, Image, Inbox, Info, Key, Landmark, Laptop, Layers,
  LayoutDashboard, LayoutGrid, LayoutList, Leaf, Link, List, ListChecks, ListTodo,
  LoaderCircle, Lock, Mail, MailOpen, Map, MapPin, Maximize2, Menu, MessageSquare, Minus,
  Monitor, Moon, Music, Package, PackageCheck, Paperclip, Pencil, Percent, Phone, PiggyBank,
  Pill, Pin, Plane, Plus, Receipt, RefreshCw, Repeat, Rocket, RotateCcw, Scale, Search, Send,
  Settings, Share2, Shield, ShieldCheck, Ship, Shirt, ShoppingBag, ShoppingCart, Sigma,
  SlidersHorizontal, Smartphone, Sparkles, SquareKanban, Star, Stethoscope, Store, Sun, Table,
  Tag, Target, Ticket, Timer, Train, TrendingDown, TrendingUp, TriangleAlert, Trophy, Truck,
  User, UserCheck, Users, Utensils, Wallet, Wrench, X, Zap,
};
// ICONS-END

/** "CalendarDays" → "calendar-days", "Building2" → "building-2". */
function kebab(name: string): string {
  return name
    .replace(/([a-z])([A-Z0-9])/g, "$1-$2")
    .replace(/([0-9])([A-Z])/g, "$1-$2")
    .toLowerCase();
}

const ICONS = new globalThis.Map(
  Object.entries(ICON_SET).map(([name, C]) => [kebab(name), C] as const),
);

/** A lucide icon by kebab-case name ("calendar-days"). An unknown name renders nothing. */
function Icon({
  name,
  size = 16,
  strokeWidth = 1.75,
  ...rest
}: { name: string; size?: number; strokeWidth?: number } & React.SVGProps<SVGSVGElement>) {
  const C = ICONS.get(String(name).toLowerCase());
  return C ? <C size={size} strokeWidth={strokeWidth} aria-hidden {...(rest as object)} /> : null;
}

export const STUDIO = {
  React,
  Fragment: React.Fragment,
  useState: React.useState,
  useMemo: React.useMemo,
  useEffect: React.useEffect,
  useLayoutEffect: React.useLayoutEffect,
  useRef: React.useRef,
  useCallback: React.useCallback,
  useReducer: React.useReducer,
  useId: React.useId,
  useTransition: React.useTransition,
  useDeferredValue: React.useDeferredValue,
  cx: clsx,
  // charts
  Recharts,
  ResponsiveContainer: Recharts.ResponsiveContainer,
  BarChart: Recharts.BarChart,
  Bar: Recharts.Bar,
  LineChart: Recharts.LineChart,
  Line: Recharts.Line,
  AreaChart: Recharts.AreaChart,
  Area: Recharts.Area,
  ComposedChart: Recharts.ComposedChart,
  PieChart: Recharts.PieChart,
  Pie: Recharts.Pie,
  Cell: Recharts.Cell,
  RadialBarChart: Recharts.RadialBarChart,
  RadialBar: Recharts.RadialBar,
  RadarChart: Recharts.RadarChart,
  Radar: Recharts.Radar,
  PolarGrid: Recharts.PolarGrid,
  PolarAngleAxis: Recharts.PolarAngleAxis,
  PolarRadiusAxis: Recharts.PolarRadiusAxis,
  ScatterChart: Recharts.ScatterChart,
  Scatter: Recharts.Scatter,
  Treemap: Recharts.Treemap,
  XAxis: Recharts.XAxis,
  YAxis: Recharts.YAxis,
  CartesianGrid: Recharts.CartesianGrid,
  Tooltip: Recharts.Tooltip,
  Legend: Recharts.Legend,
  ReferenceLine: Recharts.ReferenceLine,
  LabelList: Recharts.LabelList,
  // icons
  Icon,
  // data
  records,
  types,
  openEmail,
};

const w = window as unknown as Record<string, unknown>;
Object.assign(w, STUDIO);
w.DemuxStudio = STUDIO;

installRuntime({
  fallback: (
    <div style={{ padding: 16, font: "14px system-ui, sans-serif" }}>
      This workspace hit a display error.
    </div>
  ),
});
