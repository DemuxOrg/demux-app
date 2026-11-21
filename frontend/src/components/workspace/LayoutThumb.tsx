/**
 * Static thumbnails of the kit's layout blocks for the build flow's layout step
 * (theme.md §7.10): no real data, drawn in the palette the user picked.
 */
import type { CSSProperties, ReactNode } from "react";
import type { PaletteInfo } from "@/lib/api";

const FALLBACK = {
  accent: "#6A3DF0",
  accent_soft: "#EEE9FE",
  series: ["#6A3DF0", "#5EA7F4", "#E0679A", "#2FB36B", "#F5A524"],
};

function Box({
  className = "",
  style,
  children,
}: {
  className?: string;
  style?: CSSProperties;
  children?: ReactNode;
}) {
  return (
    <span className={`block ${className}`} style={style}>
      {children}
    </span>
  );
}

export function LayoutThumb({
  block,
  palette,
}: {
  block: string;
  palette: PaletteInfo | undefined;
}) {
  const p = palette ?? FALLBACK;
  const line = "bg-[#E2E8F0]";
  let body: ReactNode;
  switch (block) {
    case "Board":
      body = (
        <span className="grid h-full grid-cols-3 gap-1.5">
          {[3, 2, 1].map((n, c) => (
            <Box
              key={c}
              className="flex flex-col gap-1 rounded-[6px] bg-white/70 p-1"
            >
              <Box
                className="h-1 w-3 rounded-full"
                style={{ background: p.series[c + 1] }}
              />
              {Array.from({ length: n }, (_, i) => (
                <Box
                  key={i}
                  className="h-2.5 rounded-[3px] bg-white shadow-[0_0_0_1px_#E6EBF2]"
                />
              ))}
            </Box>
          ))}
        </span>
      );
      break;
    case "DataTable":
      body = (
        <span className="flex h-full flex-col justify-center gap-1.5">
          <Box className={`h-1.5 w-full rounded-full ${line}`} />
          {[0.9, 0.75, 0.85, 0.6].map((w, i) => (
            <span key={i} className="flex items-center gap-1.5">
              <Box
                className="h-1 rounded-full bg-[#CBD5E1]"
                style={{ width: `${w * 55}%` }}
              />
              <Box
                className="ml-auto h-1.5 w-5 rounded-full"
                style={{ background: p.accent_soft }}
              />
            </span>
          ))}
        </span>
      );
      break;
    case "Timeline":
      body = (
        <span className="flex h-full gap-2">
          <Box className={`ml-1 w-0.5 rounded-full ${line}`} />
          <span className="flex flex-1 flex-col justify-around">
            {[0.8, 0.6, 0.7].map((w, i) => (
              <span key={i} className="flex items-center gap-1.5">
                <Box
                  className="size-1.5 rounded-full"
                  style={{ background: i === 0 ? p.accent : "#CBD5E1" }}
                />
                <Box
                  className="h-2.5 rounded-[3px] bg-white shadow-[0_0_0_1px_#E6EBF2]"
                  style={{ width: `${w * 100}%` }}
                />
              </span>
            ))}
          </span>
        </span>
      );
      break;
    case "Calendar":
      body = (
        <span className="grid h-full grid-cols-7 gap-0.5">
          {Array.from({ length: 21 }, (_, i) => (
            <Box
              key={i}
              className="rounded-[2px]"
              style={{
                background: [4, 9, 16].includes(i)
                  ? p.accent_soft
                  : i === 11
                    ? p.accent
                    : "rgba(255,255,255,.8)",
              }}
            />
          ))}
        </span>
      );
      break;
    case "Gallery":
      body = (
        <span className="grid h-full grid-cols-3 gap-1.5">
          {[0, 1, 2].map((i) => (
            <Box
              key={i}
              className="flex flex-col gap-1 rounded-[4px] bg-white p-1 shadow-[0_0_0_1px_#E6EBF2]"
            >
              <Box className="h-1 w-3/4 rounded-full bg-[#94A3B8]" />
              <Box className="h-1 w-1/2 rounded-full bg-[#CBD5E1]" />
              <Box
                className="mt-auto h-1.5 w-4 rounded-full"
                style={{ background: p.series[i] }}
              />
            </Box>
          ))}
        </span>
      );
      break;
    case "ListDetail":
      body = (
        <span className="grid h-full grid-cols-[2fr_3fr] gap-1.5">
          <span className="flex flex-col gap-1">
            {[0, 1, 2].map((i) => (
              <Box
                key={i}
                className="h-2 rounded-[3px]"
                style={{
                  background: i === 0 ? p.accent_soft : "rgba(255,255,255,.85)",
                }}
              />
            ))}
          </span>
          <Box className="flex flex-col gap-1 rounded-[4px] bg-white p-1.5 shadow-[0_0_0_1px_#E6EBF2]">
            <Box className="h-1.5 w-2/3 rounded-full bg-[#94A3B8]" />
            <Box className="h-1 w-full rounded-full bg-[#E2E8F0]" />
            <Box className="h-1 w-5/6 rounded-full bg-[#E2E8F0]" />
          </Box>
        </span>
      );
      break;
    default:
      // Dashboard: stat boxes and bars.
      body = (
        <span className="flex h-full flex-col gap-1.5">
          <span className="grid grid-cols-3 gap-1">
            {[0, 1, 2].map((i) => (
              <Box
                key={i}
                className="h-3 rounded-[3px] bg-white shadow-[0_0_0_1px_#E6EBF2]"
              />
            ))}
          </span>
          <span className="flex flex-1 items-end gap-1">
            {[45, 80, 60, 95, 70, 50].map((h, i) => (
              <Box
                key={i}
                className="flex-1 rounded-t-[2px]"
                style={{
                  height: `${h}%`,
                  background: i === 3 ? p.accent : p.series[1],
                }}
              />
            ))}
          </span>
        </span>
      );
  }
  return (
    <span aria-hidden className="block h-16 rounded-sm bg-surface-2 p-2">
      {body}
    </span>
  );
}
