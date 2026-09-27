import { cn } from "@/lib/utils";

export type Confidence = "high" | "medium" | "low";

const styles: Record<Confidence, string> = {
  high: "bg-conf-high text-white",
  medium: "bg-conf-medium text-accent-foreground",
  low: "bg-conf-low text-white",
};

const labels: Record<Confidence, string> = {
  high: "High confidence",
  medium: "Medium confidence",
  low: "Low confidence",
};

/** Confidence badge: always colour + text, never colour alone. */
export function ConfidencePill({
  level,
  label,
  className,
}: {
  level: Confidence;
  label?: string;
  className?: string;
}) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-bold uppercase tracking-wide",
        styles[level],
        className,
      )}
    >
      <span className="h-1.5 w-1.5 rounded-full bg-current opacity-80" aria-hidden />
      {label ?? labels[level]}
    </span>
  );
}
