import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Bibliometric Research Pipeline",
  description: "Advanced bibliometric analysis with GPU acceleration",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
