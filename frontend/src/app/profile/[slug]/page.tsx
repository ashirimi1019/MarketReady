"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";

type PublicProfile = {
  username: string;
  university?: string | null;
  pathway?: string | null;
  mri_score: number;
  mri_band: string;
  mri_components: { federal_standards: number; market_demand: number; evidence_density: number };
  verified_skills: string[];
  proof_count: number;
  github_username?: string | null;
  semester?: string | null;
  profile_generated_at: string;
};

const bandColor = (band: string) => {
  if (band === "Market Ready") return "#00c896";
  if (band === "Competitive") return "#3d6dff";
  if (band === "Developing") return "#ffb300";
  return "#ff3b30";
};

function ScoreRing({ score, band }: { score: number; band: string }) {
  const color = bandColor(band);
  const r = 52;
  const stroke = 8;
  const circ = 2 * Math.PI * r;
  const offset = circ * (1 - Math.min(score / 100, 1));

  return (
    <div className="relative inline-flex items-center justify-center">
      <svg width={r * 2 + stroke + 4} height={r * 2 + stroke + 4} style={{ transform: "rotate(-90deg)" }}>
        <circle cx={r + stroke / 2 + 2} cy={r + stroke / 2 + 2} r={r} fill="none" stroke="rgba(61,109,255,0.12)" strokeWidth={stroke} />
        <circle cx={r + stroke / 2 + 2} cy={r + stroke / 2 + 2} r={r} fill="none" stroke={color} strokeWidth={stroke} strokeLinecap="round"
          strokeDasharray={circ} strokeDashoffset={offset} />
      </svg>
      <div className="absolute flex flex-col items-center">
        <span className="text-3xl font-bold" style={{ color }}>{score.toFixed(0)}</span>
        <span className="text-xs text-[color:var(--muted)]">/ 100</span>
      </div>
    </div>
  );
}

export default function PublicProfilePage() {
  const params = useParams();
  const slug = params?.slug as string;
  const [profile, setProfile] = useState<PublicProfile | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!slug) return;
    fetch(`${process.env.NEXT_PUBLIC_API_BASE}/public/${slug}`)
      .then(r => {
        if (!r.ok) throw new Error("Profile not found");
        return r.json();
      })
      .then(setProfile)
      .catch(() => setError("Profile not found or unavailable"))
      .finally(() => setLoading(false));
  }, [slug]);

  if (loading) {
    return (
      <main className="min-h-screen flex items-center justify-center" style={{ background: "var(--scene-bg)" }}>
        <div className="h-10 w-10 rounded-full border-2 border-[color:var(--primary)] border-t-transparent animate-spin" />
      </main>
    );
  }

  if (error || !profile) {
    return (
      <main className="min-h-screen flex items-center justify-center" style={{ background: "var(--scene-bg)" }}>
        <div className="text-center space-y-4">
          <p className="text-2xl font-bold">Profile Not Found</p>
          <p className="text-[color:var(--muted)]">This link may have expired or doesn't exist.</p>
          <Link href="/" className="cta cta-primary inline-block">Go Home</Link>
        </div>
      </main>
    );
  }

  const generatedDate = new Date(profile.profile_generated_at).toLocaleDateString("en-US", { month: "long", year: "numeric" });

  return (
    <main className="min-h-screen py-12 px-4" style={{ background: "var(--scene-bg)" }}>
      <div className="max-w-2xl mx-auto space-y-6">
        {/* Header */}
        <div className="rounded-2xl border border-[color:var(--border)] bg-[color:var(--surface)] p-6" data-testid="public-profile-header">
          <div className="flex items-center gap-4 mb-4">
            <div className="h-14 w-14 rounded-xl bg-gradient-to-br from-[var(--primary)] to-[var(--accent-3)] flex items-center justify-center text-white text-xl font-bold">
              {profile.username.charAt(0).toUpperCase()}
            </div>
            <div>
              <h1 className="text-2xl font-bold" data-testid="public-username">{profile.username}</h1>
              <div className="flex flex-wrap gap-2 mt-1">
                {profile.pathway && <span className="text-xs text-[color:var(--muted)] border border-[color:var(--border)] px-2 py-0.5 rounded-full">{profile.pathway}</span>}
                {profile.university && <span className="text-xs text-[color:var(--muted)] border border-[color:var(--border)] px-2 py-0.5 rounded-full">{profile.university}</span>}
                {profile.semester && <span className="text-xs text-[color:var(--muted)] border border-[color:var(--border)] px-2 py-0.5 rounded-full">{profile.semester}</span>}
              </div>
            </div>
          </div>
          <p className="text-xs text-[color:var(--muted)]">Verified by Market Ready · {generatedDate}</p>
        </div>

        {/* MRI Score */}
        <div className="rounded-2xl border border-[color:var(--border)] bg-[color:var(--surface)] p-6" data-testid="public-mri-card">
          <h2 className="text-lg font-semibold mb-4">Market-Ready Index (MRI)</h2>
          <div className="flex flex-col sm:flex-row items-center gap-6">
            <ScoreRing score={profile.mri_score} band={profile.mri_band} />
            <div className="flex-1 w-full space-y-3">
              <div className="flex items-center justify-between">
                <span className="text-sm font-medium px-2 py-1 rounded-full"
                  style={{ background: `${bandColor(profile.mri_band)}22`, color: bandColor(profile.mri_band) }}>
                  {profile.mri_band}
                </span>
                <span className="text-xs text-[color:var(--muted)]">{profile.proof_count} verified proofs</span>
              </div>
              {[
                { label: "Federal Standards", value: profile.mri_components.federal_standards, color: "#3d6dff" },
                { label: "Market Demand", value: profile.mri_components.market_demand, color: "#00c896" },
                { label: "Evidence Density", value: profile.mri_components.evidence_density, color: "#ff7b1a" },
              ].map(({ label, value, color }) => (
                <div key={label} className="space-y-1">
                  <div className="flex justify-between text-xs">
                    <span className="text-[color:var(--muted)]">{label}</span>
                    <span style={{ color }}>{value.toFixed(0)}</span>
                  </div>
                  <div className="h-1.5 rounded-full bg-[rgba(61,109,255,0.08)] overflow-hidden">
                    <div className="h-full rounded-full" style={{ width: `${value}%`, background: color }} />
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Verified Skills */}
        {profile.verified_skills.length > 0 && (
          <div className="rounded-2xl border border-[color:var(--border)] bg-[color:var(--surface)] p-6" data-testid="public-skills-card">
            <h2 className="text-lg font-semibold mb-3">Verified Skills</h2>
            <div className="flex flex-wrap gap-2">
              {profile.verified_skills.map(skill => (
                <span key={skill} className="px-3 py-1 rounded-full text-sm border border-[rgba(0,200,150,0.3)] bg-[rgba(0,200,150,0.07)] text-[color:var(--success)]">
                  {skill}
                </span>
              ))}
            </div>
          </div>
        )}

        {/* GitHub */}
        {profile.github_username && (
          <div className="rounded-2xl border border-[color:var(--border)] bg-[color:var(--surface)] p-6" data-testid="public-github-card">
            <h2 className="text-lg font-semibold mb-2">Engineering Signal</h2>
            <a
              href={`https://github.com/${profile.github_username}`}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-2 text-sm text-[color:var(--primary)] hover:opacity-80 transition-opacity"
            >
              <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
                <path d="M12 0C5.37 0 0 5.37 0 12c0 5.31 3.435 9.795 8.205 11.385.6.105.825-.255.825-.57 0-.285-.015-1.23-.015-2.235-3.015.555-3.795-.735-4.035-1.41-.135-.345-.72-1.41-1.23-1.695-.42-.225-1.02-.78-.015-.795.945-.015 1.62.87 1.845 1.23 1.08 1.815 2.805 1.305 3.495.99.105-.78.42-1.305.765-1.605-2.67-.3-5.46-1.335-5.46-5.925 0-1.305.465-2.385 1.23-3.225-.12-.3-.54-1.53.12-3.18 0 0 1.005-.315 3.3 1.23.96-.27 1.98-.405 3-.405s2.04.135 3 .405c2.295-1.56 3.3-1.23 3.3-1.23.66 1.65.24 2.88.12 3.18.765.84 1.23 1.905 1.23 3.225 0 4.605-2.805 5.625-5.475 5.925.435.375.81 1.095.81 2.22 0 1.605-.015 2.895-.015 3.3 0 .315.225.69.825.57A12.02 12.02 0 0 0 24 12c0-6.63-5.37-12-12-12z"/>
              </svg>
              github.com/{profile.github_username}
            </a>
          </div>
        )}

        <div className="text-center pt-4">
          <p className="text-xs text-[color:var(--muted)]">Profile verified by Market Ready · Built for proof-first hiring</p>
          <Link href="/" className="mt-2 inline-block text-xs text-[color:var(--primary)] hover:opacity-80">
            Get your Market Ready profile
          </Link>
        </div>
      </div>
    </main>
  );
}
