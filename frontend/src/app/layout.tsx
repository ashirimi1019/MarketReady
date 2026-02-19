import type { Metadata } from "next";
import { Space_Grotesk, IBM_Plex_Mono } from "next/font/google";
import "./globals.css";
import NavBar from "@/components/NavBar";

const spaceGrotesk = Space_Grotesk({
  variable: "--font-space",
  display: "swap",
  weight: ["400", "500", "600", "700"],
  fallback: ["Segoe UI", "Arial", "sans-serif"],
  subsets: ["latin"],
});

const ibmPlexMono = IBM_Plex_Mono({
  variable: "--font-plex-mono",
  display: "swap",
  weight: ["400", "600"],
  fallback: ["Consolas", "Courier New", "monospace"],
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "Market Ready",
  description: "Proof-first career acceleration with OpenAI-powered market signals",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" data-theme="dark">
      <body
        className={`${spaceGrotesk.variable} ${ibmPlexMono.variable} antialiased`}
      >
        <div className="page-shell">
          <NavBar />
          {children}
        </div>
      </body>
    </html>
  );
}
