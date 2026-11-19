import type { Metadata } from "next";
import { Plus_Jakarta_Sans, Public_Sans, JetBrains_Mono } from "next/font/google";
import "./globals.css";

const plusJakarta = Plus_Jakarta_Sans({
  subsets: ["latin"],
  weight: ["600", "700"],
  variable: "--font-display",
});

const publicSans = Public_Sans({
  subsets: ["latin"],
  weight: ["400", "500", "600"],
  variable: "--font-body",
});

const jetbrainsMono = JetBrains_Mono({
  subsets: ["latin"],
  weight: ["400", "500"],
  variable: "--font-mono",
});

export const metadata: Metadata = {
  title: "CineForge Enterprise AI Video Engine",
  description:
    "Enterprise AI Video Production Engine merging AI-Content-Studio and ContentMachine with PostgreSQL JSONB Master Manifest, Content-Addressed Multimodal Context Ingestion, and S3/R2 Asset Mirroring.",
  openGraph: {
    title: "CineForge Enterprise AI Video Engine",
    description:
      "Enterprise AI Video Production Engine merging AI-Content-Studio and ContentMachine with PostgreSQL JSONB Master Manifest, Content-Addressed Multimodal Context Ingestion, and S3/R2 Asset Mirroring.",
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="en"
      className={`${plusJakarta.variable} ${publicSans.variable} ${jetbrainsMono.variable}`}
    >
      <body className="min-h-screen bg-slate-50 text-slate-900 antialiased selection:bg-slate-900 selection:text-white">
        {children}
      </body>
    </html>
  );
}
