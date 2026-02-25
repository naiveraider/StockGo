import "./globals.css";
import type { ReactNode } from "react";
import { TopNav } from "../components/TopNav";

export const metadata = {
  title: "StockGo",
  description: "US stocks analyzer powered by FastAPI + GPT"
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
      <body>
        <TopNav />
        <main className="mx-auto max-w-6xl px-4 py-6">{children}</main>
      </body>
    </html>
  );
}

