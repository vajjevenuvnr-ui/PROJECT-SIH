import { cookies } from "next/headers";

import { AlertBanner, AlertProvider } from "@/components/alerts/AlertCenter";
import { DemoGuide } from "@/components/layout/DemoGuide";
import { BottomNav, Sidebar } from "@/components/layout/Navigation";
import { TopBar } from "@/components/layout/TopBar";
import { AppProviders } from "@/components/providers/AppProviders";
import { DEMO_DATA_COOKIE, DEMO_SESSION_COOKIE } from "@/lib/session";

// Shell for every officer screen (S1-S6). Access is enforced in src/middleware.ts.
export default function OfficerLayout({ children }: { children: React.ReactNode }) {
  const jar = cookies();
  const demoSession = jar.get(DEMO_SESSION_COOKIE)?.value === "demo";
  const demoData = jar.get(DEMO_DATA_COOKIE)?.value === "1" || process.env.NEXT_PUBLIC_DEMO_MODE === "true";

  return (
    <AppProviders initialDemo={demoData} demoSession={demoSession}>
      <AlertProvider>
      <div className="min-h-screen bg-background">
        <TopBar />
        <AlertBanner />
        <div className="flex">
          <Sidebar />
          <main className="min-w-0 flex-1 px-4 pb-24 pt-5 sm:px-6 md:pb-10 lg:px-8">{children}</main>
        </div>
        <BottomNav />
        <DemoGuide />
      </div>
      </AlertProvider>
    </AppProviders>
  );
}
