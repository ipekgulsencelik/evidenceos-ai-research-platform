import type { Metadata } from "next";

import "./globals.css";

export const metadata: Metadata = {
  title: "EvidenceOS | Academic Research",
  description: "Evidence-first academic discovery and DOI metadata verification.",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
