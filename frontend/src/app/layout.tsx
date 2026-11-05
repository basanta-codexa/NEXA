import type { Metadata } from "next";
import { Fraunces, Instrument_Sans } from "next/font/google";
import "./globals.css";

const fraunces = Fraunces({
  subsets: ["latin"],
  variable: "--font-fraunces",
  display: "swap",
});

const instrumentSans = Instrument_Sans({
  subsets: ["latin"],
  variable: "--font-instrument",
  display: "swap",
});

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
    <html lang="en" className={`${fraunces.variable} ${instrumentSans.variable}`}>
      <body>{children}</body>
    </html>
  );
}
