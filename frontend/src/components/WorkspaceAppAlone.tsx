"use client";

/**
 * One workspace's app in the whole window, nothing around it (theme.md §8.4b). Same
 * loading and refresh as the workspace page (`useWorkspace`). The tab is titled with
 * the workspace name. Anything that needs Demux (a build in progress, a failed build,
 * fixing a display error) links back to the workspace page.
 */
import { useCallback, useEffect, useState } from "react";
import { AppFrame } from "@/components/AppFrame";
import { LogoMark } from "@/components/brand/Logo";
import { ButtonLink } from "@/components/ui/Button";
import { Spinner } from "@/components/ui/Spinner";
import { FloatingBanners } from "@/components/WorkspaceDetail";
import { useWorkspace } from "@/lib/useWorkspace";

export function WorkspaceAppAlone({ id }: { id: string }) {
  const { ws, app, data, shell, error } = useWorkspace(id);
  const [appError, setAppError] = useState<string | null>(null);
  const onAppError = useCallback((m: string | null) => setAppError(m), []);
  const href = `/workspaces/${id}`;

  const name = ws?.name;
  useEffect(() => {
    if (name) document.title = name;
  }, [name]);

  if (error && !ws) return <Notice title={error} href={href} />;
  if (!ws)
    return (
      <div className="grid min-h-dvh place-items-center" aria-label="Loading">
        <Spinner size={28} />
      </div>
    );
  if (ws.status === "building" || ws.active_run?.kind === "build")
    return (
      <Notice
        title="This workspace is still being built"
        body="It opens here on its own once it's ready."
        href={href}
      />
    );
  if (ws.status === "failed")
    return <Notice title="This workspace couldn't be built" href={href} />;

  return (
    <main className="relative h-dvh">
      <section aria-label={ws.name} className="absolute inset-0">
        {app?.html && shell && data ? (
          <AppFrame
            shellHead={shell.head}
            html={app.html}
            appVersion={app.version}
            palette={ws.palette}
            data={data.data}
            onError={onAppError}
          />
        ) : (
          <div
            className="grid h-full place-items-center"
            aria-label="Loading the app"
          >
            <Spinner size={24} />
          </div>
        )}
      </section>
      {appError && (
        <FloatingBanners>
          <div
            role="alert"
            className="flex animate-dmx-rise flex-wrap items-center gap-3 rounded-md bg-danger-bg py-1.5 pr-1.5 pl-4 text-sm text-danger shadow-input"
          >
            <span className="min-w-0 flex-1">
              This workspace hit a display error.
            </span>
            <ButtonLink href={href} size="sm">
              Open in Demux
            </ButtonLink>
          </div>
        </FloatingBanners>
      )}
    </main>
  );
}

function Notice({
  title,
  body,
  href,
}: {
  title: string;
  body?: string;
  href: string;
}) {
  return (
    <main className="grid min-h-dvh place-items-center px-4">
      <section className="w-full max-w-[440px] rounded-[30px] bg-surface px-8 pt-9 pb-8 shadow-float">
        <LogoMark size={46} />
        <h1 className="mt-6 text-[24px] leading-[1.2] font-medium tracking-[-0.02em]">
          {title}
        </h1>
        {body && <p className="mt-2 text-base text-ink-2">{body}</p>}
        <div className="mt-6">
          <ButtonLink href={href} variant="secondary">
            Open in Demux
          </ButtonLink>
        </div>
      </section>
    </main>
  );
}
