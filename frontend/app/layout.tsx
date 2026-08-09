import type { Metadata } from "next";
import "./globals.css";
import Sidebar from "@/components/layout/Sidebar";
import TopBar from "@/components/layout/TopBar";

export const metadata: Metadata = {
  title: "HR AI Operating System",
  description: "Enterprise-grade recruiting platform backed by intelligent model routing",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className="h-full bg-bg-base text-slate-100">
      <body className="h-full flex overflow-hidden font-sans">
        {/* Navigation Sidebar */}
        <Sidebar />

        {/* Core Layout */}
        <div className="flex-1 flex flex-col pl-64 relative min-h-screen">
          {/* Header Telemetry Bar */}
          <TopBar />

          {/* Main Content Workspace */}
          <main className="flex-1 overflow-y-auto mt-16 p-8 mesh-bg">
            <div className="max-w-7xl mx-auto w-full animate-fade-in">
              {children}
            </div>
          </main>
        </div>
      </body>
    </html>
  );
}
