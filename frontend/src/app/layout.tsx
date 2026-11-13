/**
 * Root layout: global CSS, fonts, metadata and the top nav shared by all routes.
 * Pages control their own width (the workspace view is full width).
 */
import type { Metadata } from "next";
import Link from "next/link";
import { Geist } from "next/font/google";
import { NavUser } from "@/components/NavUser";
import "./globals.css";

const geistSans = Geist({ variable: "--font-geist-sans", subsets: ["latin"] });

export const metadata: Metadata = {
  title: "Demux",
  description: "Turn your Gmail into structured, refreshable workspaces.",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="en" className={`${geistSans.variable} h-full antialiased`}>
      <body className="min-h-full bg-white text-gray-900">
        <header className="h-[49px] border-b border-gray-200">
          <nav className="flex h-full items-center gap-6 px-4 text-sm">
            <Link href="/" className="font-semibold">
              Demux
            </Link>
            <Link href="/workspaces" className="text-gray-600 hover:text-gray-900">
              Workspaces
            </Link>
            <NavUser />
          </nav>
        </header>
        <main>{children}</main>
      </body>
    </html>
  );
}
