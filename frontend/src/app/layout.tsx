import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: {
    default: "NEXA — AI workforce platform",
    template: "%s · NEXA",
  },
  description:
    "NEXA is a multi-tenant platform for building, running and voicing AI agents with tools, persistent memory and retrieval-augmented knowledge.",
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
