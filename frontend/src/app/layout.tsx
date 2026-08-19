import type { Metadata } from "next";
import "./globals.css";
import { UserProvider } from "../lib/userContext";
import { Sidebar } from "../components/layout/Sidebar";

export const metadata: Metadata = {
  title: "Web Radar — Persistent Web Monitoring & Semantic Alerts",
  description:
    "Autonomous web monitor backed by Bright Data Scraper Studio custom scrapers and Neon PostgreSQL. Watches the web while you're away and alerts only on meaningful changes.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className="dark">
      <body className="bg-space-950 text-slate-100 antialiased min-h-screen flex selection:bg-radar-cyan selection:text-space-950">
        <UserProvider>
          {/* Main App Layout */}
          <div className="flex w-full min-h-screen">
            {/* Sidebar */}
            <Sidebar />

            {/* Content Area */}
            <main className="flex-1 flex flex-col min-w-0 bg-space-950 overflow-y-auto">
              {children}
            </main>
          </div>
        </UserProvider>
      </body>
    </html>
  );
}
