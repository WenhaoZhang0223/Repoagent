import type { Metadata } from "next";
import "./styles.css";

export const metadata: Metadata = {
  title: "Repo Learning Agent",
  description: "Generate learning docs from a public GitHub repository."
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="zh-CN">
      <body>{children}</body>
    </html>
  );
}

