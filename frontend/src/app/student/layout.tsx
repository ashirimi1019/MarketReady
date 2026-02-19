"use client";

import { useSession } from "@/lib/session";
import Link from "next/link";

export default function StudentLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const { isLoggedIn } = useSession();

  return (
    <div className="page-shell">
      {!isLoggedIn && (
        <>
          <header className="flex flex-col gap-3">
            <span className="badge">Student Portal</span>
            <h1 className="text-3xl font-semibold">Your Pathway</h1>
            <nav className="flex flex-wrap gap-3 text-sm text-[color:var(--muted)]">
              <Link href="/login">Login</Link>
              <Link href="/">Home</Link>
              <Link href="/#student-flow">How it works</Link>
            </nav>
          </header>
          <div className="divider" />
        </>
      )}
      <main className={isLoggedIn ? "mt-6" : "mt-8"}>{children}</main>
    </div>
  );
}
