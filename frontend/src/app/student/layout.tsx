"use client";

import { useSession } from "@/lib/session";
import Link from "next/link";

export default function StudentLayout({ children }: { children: React.ReactNode }) {
  const { isLoggedIn } = useSession();

  if (!isLoggedIn) {
    return (
      <div>
        <header className="mb-6 flex flex-col gap-3">
          <span className="badge">Student Portal</span>
          <h1 className="text-3xl font-bold tracking-tight">Your Pathway</h1>
          <nav className="flex flex-wrap gap-4 text-sm" style={{ color: "var(--muted)" }}>
            <Link href="/login" className="hover:text-[color:var(--primary)] transition-colors">Login</Link>
            <Link href="/" className="hover:text-[color:var(--primary)] transition-colors">Home</Link>
            <Link href="/#student-flow" className="hover:text-[color:var(--primary)] transition-colors">How it works</Link>
          </nav>
        </header>
        <div className="divider" />
        <main>{children}</main>
      </div>
    );
  }

  return <main>{children}</main>;
}
