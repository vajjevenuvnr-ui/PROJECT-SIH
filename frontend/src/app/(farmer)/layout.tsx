import { ThemeScript } from "@/components/theme/theme-script";

import "../globals.css";

// Farmer page root layout: no officer shell, no NextIntl client bundle and NO web-font downloads.
// Android ships Noto Sans Telugu / Devanagari (Windows: Nirmala UI, iOS: Telugu/Devanagari Sangam),
// so the page uses the phone's own fonts and stays small on 2G/3G.
const SYSTEM_FONTS = {
  "--font-inter": "ui-sans-serif, system-ui, -apple-system, Roboto, 'Segoe UI', sans-serif",
  "--font-telugu": "'Noto Sans Telugu', 'Nirmala UI', 'Telugu Sangam MN', Gautami, sans-serif",
  "--font-devanagari": "'Noto Sans Devanagari', 'Nirmala UI', 'Devanagari Sangam MN', Mangal, sans-serif",
} as React.CSSProperties;

export default function FarmerLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="te" data-theme="light" suppressHydrationWarning>
      <head>
        <ThemeScript />
      </head>
      <body className="font-sans" style={SYSTEM_FONTS}>
        {children}
      </body>
    </html>
  );
}
