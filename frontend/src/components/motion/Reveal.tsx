/**
 * Entrances (theme.md §9). CSS-only, so they work in server components and cost nothing
 * after the first paint. They play once when the element mounts; re-renders from
 * polling don't replay them.
 *
 * - <Reveal index={n}>: a block that fades and rises in, `n` steps of 80ms after the
 *   screen appears. Number blocks in reading order (title 0, card 1, helper line 2…).
 * - <RevealText>: a page title whose words resolve one after another (fade, rise,
 *   blur → sharp). Screen readers get the plain text once; the animated words are
 *   hidden from them.
 */
import type { CSSProperties, ElementType, ReactNode } from "react";

export const REVEAL_STEP_MS = 80;
const WORD_STEP_MS = 45;

type Delay = { "--dmx-delay": string };

export function Reveal({
  index = 0,
  delay = 0,
  as: Tag = "div",
  className = "",
  children,
}: {
  index?: number;
  /** Extra delay in ms, added after `index` steps. */
  delay?: number;
  as?: ElementType;
  className?: string;
  children: ReactNode;
}) {
  const style: CSSProperties & Delay = {
    "--dmx-delay": `${index * REVEAL_STEP_MS + delay}ms`,
  };
  return (
    <Tag className={`dmx-reveal ${className}`} style={style}>
      {children}
    </Tag>
  );
}

export function RevealText({
  text,
  as: Tag = "h1",
  delay = 0,
  className = "",
}: {
  text: string;
  as?: ElementType;
  /** Delay in ms before the first word. */
  delay?: number;
  className?: string;
}) {
  const words = text.split(/\s+/).filter(Boolean);
  return (
    <Tag className={className}>
      <span className="sr-only">{text}</span>
      <span aria-hidden>
        {words.map((word, i) => (
          <span key={i}>
            <span
              className="dmx-reveal-word"
              style={
                {
                  "--dmx-delay": `${delay + i * WORD_STEP_MS}ms`,
                } as CSSProperties & Delay
              }
            >
              {word}
            </span>
            {i < words.length - 1 ? " " : null}
          </span>
        ))}
      </span>
    </Tag>
  );
}
