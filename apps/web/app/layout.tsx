import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Friday Workspace",
  description: "Friday premium enterprise conversation workspace"
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
