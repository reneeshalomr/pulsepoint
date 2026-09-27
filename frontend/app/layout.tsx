import type { Metadata } from "next";
import "./globals.css";
export const metadata: Metadata = {
  title: "PULSEPOINT — A better clinical conversation",
  description:
    "A question-driven clinical collaboration demo. Evidence, expert perspective, and a clearer next step.",
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
