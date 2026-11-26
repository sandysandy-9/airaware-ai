import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "AirAware AI — Intelligent Urban Air Quality & Personalised Action Assistant",
  description:
    "Indicative urban air quality intelligence platform using CPCB NAQI breakpoints on Copernicus CAMS Global model-derived estimates, deterministic health guidance, and server-grounded AI.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className="dark">
      <body className="min-h-screen bg-navy-950 text-slate-100 antialiased selection:bg-cyan-500 selection:text-slate-950">
        <a
          href="#main-content"
          className="sr-only focus:not-sr-only focus:fixed focus:top-3 focus:left-3 focus:z-[60] focus:px-4 focus:py-2 focus:rounded-xl focus:bg-cyan-500 focus:text-slate-950 focus:font-bold focus:text-xs"
        >
          Skip to main content
        </a>
        {children}
      </body>
    </html>
  );
}
