import type { Metadata } from "next";
import "./globals.css";
import "./dashboard.css";
import "./palette.css";
export const metadata: Metadata = {
  title: "CLINIQ — Evidence when you ask. Expertise when it matters.",
  description: "Evidence when you ask. Expertise when it matters.",
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
