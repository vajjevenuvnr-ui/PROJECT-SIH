import { CheckCircle2, CloudRain, Send } from "lucide-react";
import type { Metadata } from "next";

import { Logo } from "@/components/brand/Logo";
import { ConfidencePill } from "@/components/data/ConfidencePill";
import { RainLegend, TempLegend } from "@/components/data/Legends";
import { ThemeToggle } from "@/components/theme/ThemeToggle";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

export const metadata: Metadata = { title: "Style guide" };

// Developer page for checking the design system. Not part of the demo flow.
const tokens = [
  "color-primary",
  "color-primary-foreground",
  "color-accent",
  "color-background",
  "color-surface",
  "color-surface-2",
  "color-foreground",
  "color-muted",
  "color-border",
  "color-success",
  "color-warning",
  "color-danger",
  "color-info",
  "color-conf-high",
  "color-conf-medium",
  "color-conf-low",
];

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="flex flex-col gap-4">
      <h2 className="text-lg font-bold">{title}</h2>
      {children}
    </section>
  );
}

export default function StyleguidePage() {
  return (
    <main className="mx-auto flex max-w-5xl flex-col gap-10 px-4 py-8 sm:px-6">
      <header className="flex items-center justify-between gap-4">
        <Logo size="md" priority />
        <div className="flex items-center gap-3">
          <span className="hidden text-sm text-muted sm:inline">Theme</span>
          <ThemeToggle />
        </div>
      </header>

      <div>
        <h1 className="text-2xl font-bold sm:text-3xl">Design system</h1>
        <p className="mt-1 text-muted">
          All colours come from <code className="rounded bg-surface-2 px-1">src/styles/theme.css</code>. Edit that file
          to change the palette.
        </p>
      </div>

      <Section title="Logo (both variants)">
        <div className="grid gap-4 sm:grid-cols-2">
          <div className="flex h-28 items-center justify-center rounded-card border bg-white">
            <Logo variant="light" size="md" />
          </div>
          <div className="flex h-28 items-center justify-center rounded-card border bg-[#0D1417]">
            <Logo variant="dark" size="md" />
          </div>
        </div>
        <div className="flex h-24 items-center justify-center rounded-card bg-primary">
          <Logo variant="dark" size="md" />
        </div>
      </Section>

      <Section title="Colour tokens">
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          {tokens.map((t) => (
            <div key={t} className="overflow-hidden rounded-xl border bg-surface">
              <div className="h-14 border-b" style={{ background: `rgb(var(--${t}))` }} />
              <div className="px-3 py-2 font-mono text-[11px] text-muted">--{t}</div>
            </div>
          ))}
        </div>
      </Section>

      <Section title="Buttons">
        <div className="flex flex-wrap gap-3">
          <Button>
            Open Block Dashboard
          </Button>
          <Button variant="accent">
            <Send /> Send to farmers
          </Button>
          <Button variant="secondary">Secondary</Button>
          <Button variant="ghost">Ghost</Button>
          <Button variant="danger">Danger</Button>
          <Button disabled>Disabled</Button>
        </div>
      </Section>

      <Section title="Cards, badges and confidence">
        <div className="grid gap-4 sm:grid-cols-3">
          <Card>
            <CardHeader>
              <CardDescription>Panchayats covered</CardDescription>
              <CardTitle className="text-3xl font-bold">24 GPs</CardTitle>
            </CardHeader>
          </Card>
          <Card>
            <CardHeader>
              <CardDescription>Active alerts</CardDescription>
              <CardTitle className="text-3xl font-bold text-warning">3</CardTitle>
            </CardHeader>
          </Card>
          <Card>
            <CardHeader>
              <CardDescription>Model run</CardDescription>
              <CardTitle className="flex items-center gap-2 text-xl font-bold">
                <CheckCircle2 className="h-5 w-5 text-success" /> OK 06:04
              </CardTitle>
            </CardHeader>
          </Card>
        </div>
        <Card>
          <CardContent className="flex flex-wrap items-center gap-2 pt-5">
            <ConfidencePill level="high" />
            <ConfidencePill level="medium" />
            <ConfidencePill level="low" />
            <Badge variant="danger">AVOID</Badge>
            <Badge variant="warning">PREPARE</Badge>
            <Badge variant="success">DO NOW</Badge>
            <Badge variant="primary">DEMO</Badge>
            <Badge variant="info">
              <CloudRain className="h-3 w-3" /> 72% chance &gt;10 mm
            </Badge>
          </CardContent>
        </Card>
      </Section>

      <Section title="Data scales">
        <Card>
          <CardContent className="flex flex-col gap-6 pt-5">
            <RainLegend />
            <TempLegend />
          </CardContent>
        </Card>
      </Section>

      <Section title="Typography and scripts">
        <Card>
          <CardContent className="flex flex-col gap-3 pt-5">
            <p className="text-3xl font-bold">38 mm · 72%</p>
            <p>English: Postpone pesticide spray until Thursday.</p>
            <p className="font-telugu text-lg" lang="te">
              తెలుగు: గురువారం వరకు పురుగుమందు పిచికారీ వాయిదా వేయండి.
            </p>
            <p className="font-devanagari text-lg" lang="hi">
              हिन्दी: गुरुवार तक कीटनाशक छिड़काव टाल दें।
            </p>
            <p className="text-sm text-muted">Muted secondary text for labels and captions.</p>
          </CardContent>
        </Card>
      </Section>
    </main>
  );
}
