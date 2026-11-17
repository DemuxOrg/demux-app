"use client";

/** Top-right of the nav: the signed-in address and "Sign out". */
import { useEffect, useState } from "react";
import { api, type Me } from "@/lib/api";

export function NavUser() {
  const [me, setMe] = useState<Me | null>(null);
  useEffect(() => {
    api.me().then(setMe).catch(() => setMe(null));
  }, []);
  if (!me) return null;
  return (
    <div className="ml-auto flex items-center gap-3 text-gray-600">
      <span>{me.email}</span>
      <button
        className="hover:text-gray-900"
        onClick={async () => {
          await api.logout().catch(() => undefined);
          window.location.href = "/";
        }}
      >
        Sign out
      </button>
    </div>
  );
}
