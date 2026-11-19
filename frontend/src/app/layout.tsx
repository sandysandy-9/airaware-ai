import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "AirAware AI — Intelligent Urban Air Quality & Personalised Action Assistant",
  description:
    "Real-time urban air quality intelligence platform using official CPCB NAQI methodology with deterministic health recommendations and grounded AI.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className="dark">
      <body className="min-h-screen bg-navy-950 text-slate-100 antialiased selection:bg-cyan-500 selection:text-slate-950">
        {children}
      </body>
    </html>
  );
}
