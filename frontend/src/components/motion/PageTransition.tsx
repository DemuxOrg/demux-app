/**
 * Calm page and step transitions on top of React's <ViewTransition> (see the CSS in
 * globals.css). Route navigations are transitions, so pages animate automatically.
 * For steps inside one page, change `stepKey` inside `startTransition`.
 * Browsers without the View Transitions API simply switch without animating.
 */
import { ViewTransition, type ReactNode } from "react";

export function PageTransition({ children }: { children: ReactNode }) {
  return (
    <ViewTransition enter="dmx-page" exit="dmx-page" default="none">
      {children}
    </ViewTransition>
  );
}

export function StepTransition({
  stepKey,
  children,
}: {
  stepKey: string;
  children: ReactNode;
}) {
  return (
    <ViewTransition
      key={stepKey}
      enter="dmx-step"
      exit="dmx-step"
      default="none"
    >
      {children}
    </ViewTransition>
  );
}
