"use client";

/**
 * Landing page (`/`).
 * Responsible for showing whether the backend is reachable (calls GET /health) and
 * linking to /workspaces. A client component because it fetches in the browser.
 */
import Link from "next/link";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";

type Health = "checking" | "ok" | "down";

export default function Home() {
  const [health, setHealth] = useState<Health>("checking");

  useEffect(() => {
    api
      .health()
      .then((h) => setHealth(h.status === "ok" ? "ok" : "down"))
      .catch(() => setHealth("down"));
  }, []);

  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-semibold">Demux</h1>
      <p className="text-gray-600">
        Backend status:{" "}
        <span
          className={
            health === "ok"
              ? "font-medium text-green-600"
              : health === "down"
                ? "font-medium text-red-600"
                : "text-gray-500"
          }
        >
          {health}
        </span>
      </p>
      <Link
        href="/workspaces"
        className="inline-block text-blue-600 hover:underline"
      >
        Go to workspaces →
      </Link>
    </div>
  );
}
