import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Incident Commander",
  description: "Operational incident dashboard for service health and investigations.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body className="font-sans">{children}</body>
    </html>
  );
}
