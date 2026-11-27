/**
 * Root layout: Instrument Sans, global tokens, and the sky backdrop with grain that
 * stays put while pages transition on top of it (theme.md §4, §5).
 */
import type { Metadata, Viewport } from "next";
import { Instrument_Sans } from "next/font/google";
import "./globals.css";

const instrumentSans = Instrument_Sans({
  subsets: ["latin"],
  weight: ["400", "500", "600"],
  variable: "--font-instrument-sans",
  display: "swap",
});

export const metadata: Metadata = {
  title: { default: "Demux", template: "%s · Demux" },
  description:
    "Turn your inbox into workspaces that keep themselves up to date.",
};

export const viewport: Viewport = { themeColor: "#5EA7F4" };

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="en" className={instrumentSans.variable}>
      <body className="bg-sky bg-grain min-h-dvh text-ink antialiased">
        {/* The sky, still, on its own layer under the grain (theme.md §4.1). */}
        <div aria-hidden className="dmx-sky" />
        <div className="relative z-10 flex min-h-dvh flex-col">{children}</div>
      </body>
    </html>
  );
}
