"use client";

import { useSession } from "@/lib/session";

export default function AdminLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const { username, isLoggedIn } = useSession();

  return (
    <div className="page-shell">
      <header className="flex flex-col gap-3">
        <span className="badge">Admin Console</span>
        <h1 className="text-3xl font-semibold">
          {isLoggedIn ? `Admin Console for ${username}` : "Control Center"}
        </h1>
        <nav className="flex flex-wrap gap-3 text-sm text-[color:var(--muted)]">
          <a href="/admin/skills">Skills</a>
          <a href="/admin/checklists">Checklists</a>
          <a href="/admin/proofs">Proofs</a>
          <a href="/admin/market">Market</a>
        </nav>
      </header>
      <div className="divider" />
      <main className="mt-8">{children}</main>
    </div>
  );
}
