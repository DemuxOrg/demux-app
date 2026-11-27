"use client";

/**
 * The workspace's app frame, live (theme.md §7.10).
 *
 * - During a build it starts with the preview app (one list per record type) and records
 *   filling in. When the generated app arrives it loads in a second, hidden frame; once
 *   that one reports rendered it crossfades in (300 ms) and the old frame is dropped:
 *   one swap per build, never a blank frame. A later app change swaps the same way.
 * - Each frame keeps its own copy of the shell and app it was made with, so nothing
 *   reloads an iframe except a new app. The same frame stays from build to ready.
 * - `cover` (before the first record): shown over the frames, which boot underneath.
 */
import { useCallback, useEffect, useState, type ReactNode } from "react";
import { AppFrame } from "@/components/AppFrame";
import type { AppDoc } from "@/lib/api";

type Doc = { key: string; head: string; html: string; version: number };
const SWAP_MS = 300;

export function LiveFrame({
  app,
  shellHead,
  data,
  changed,
  palette,
  cover,
  onError,
}: {
  app: AppDoc | null;
  shellHead: string | null;
  data: unknown;
  changed: string[];
  palette: string;
  cover: ReactNode | null;
  onError: (message: string | null) => void;
}) {
  const [frames, setFrames] = useState<Doc[]>([]);
  const [front, setFront] = useState<string | null>(null);

  // A new app (or the first): add a frame for it. The first one shows at once.
  const key =
    app?.html && shellHead
      ? `${app.version}:${app.provisional ? "p" : "a"}:${app.html.length}`
      : null;
  if (key && app?.html && shellHead && !frames.some((f) => f.key === key)) {
    const doc = { key, head: shellHead, html: app.html, version: app.version };
    setFrames([...frames, doc]);
    if (!front) setFront(key);
  }

  // After the crossfade, drop the frames behind the one in front.
  useEffect(() => {
    if (!front) return;
    const t = setTimeout(
      () =>
        setFrames((fs) =>
          fs.length > 1 ? fs.filter((f) => f.key === front) : fs,
        ),
      SWAP_MS + 20,
    );
    return () => clearTimeout(t);
  }, [front]);

  const newest = frames.at(-1)?.key ?? null;
  const promote = useCallback(
    (k: string) => setFront((cur) => (cur === k ? cur : k)),
    [],
  );
  const quiet = useCallback(() => undefined, []);

  return (
    <div className="relative h-full w-full">
      {frames.map((f) => {
        const shown = f.key === front;
        return (
          <div
            key={f.key}
            aria-hidden={shown ? undefined : true}
            className={`absolute inset-0 transition-opacity duration-300 ease-dmx motion-reduce:transition-none ${
              shown ? "opacity-100" : "pointer-events-none opacity-0"
            }`}
          >
            <AppFrame
              shellHead={f.head}
              html={f.html}
              appVersion={f.version}
              palette={palette}
              data={data}
              changed={changed}
              onError={shown ? onError : quiet}
              onRendered={f.key === newest ? () => promote(f.key) : undefined}
            />
          </div>
        );
      })}
      {cover && (
        <div className="absolute inset-0 grid place-items-center bg-surface">
          {cover}
        </div>
      )}
    </div>
  );
}
