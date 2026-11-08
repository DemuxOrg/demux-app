/**
 * Root layout: wraps every page. Responsible for global CSS, fonts, page metadata
 * and the simple centered container + top nav shared by all routes.
 */
import type { Metadata } from "next";
import Link from "next/link";
import { Geist } from "next/font/google";
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
        <header className="border-b border-gray-200">
          <nav className="mx-auto flex max-w-3xl items-center gap-6 px-4 py-3 text-sm">
            <Link href="/" className="font-semibold">
              Demux
            </Link>
            <Link
              href="/workspaces"
              className="text-gray-600 hover:text-gray-900"
            >
              Workspaces
            </Link>
          </nav>
        </header>
        <main className="mx-auto max-w-3xl px-4 py-8">{children}</main>
      </body>
    </html>
  );
}
