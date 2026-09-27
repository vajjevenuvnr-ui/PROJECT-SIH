import Image from "next/image";

import { brand } from "@/config/brand";
import { cn } from "@/lib/utils";

const heights = { sm: 28, md: 40, lg: 64 } as const;

type LogoProps = {
  size?: keyof typeof heights;
  /**
   * auto    - matches the theme (light logo in light theme)
   * inverse - opposite of the theme, for use on a bg-primary panel
   * light / dark - force one file
   */
  variant?: "auto" | "inverse" | "light" | "dark";
  className?: string;
  priority?: boolean;
};

export function Logo({ size = "md", variant = "auto", className, priority }: LogoProps) {
  const h = heights[size];
  const w = Math.round(h * brand.logoRatio);
  const style = { height: h, width: "auto" } as const;

  if (variant === "light" || variant === "dark") {
    return (
      <Image
        src={variant === "dark" ? brand.logoDark : brand.logoLight}
        alt={brand.name}
        width={w}
        height={h}
        priority={priority}
        className={cn("select-none", className)}
        style={style}
      />
    );
  }

  // Render both; CSS shows the one matching the active theme (no flash, no hydration mismatch).
  const [first, second] = variant === "inverse" ? [brand.logoDark, brand.logoLight] : [brand.logoLight, brand.logoDark];
  return (
    <span className={cn("inline-flex", className)}>
      <Image
        src={first}
        alt={brand.name}
        width={w}
        height={h}
        priority={priority}
        className="select-none dark:hidden"
        style={style}
      />
      <Image
        src={second}
        alt=""
        aria-hidden
        width={w}
        height={h}
        priority={priority}
        className="hidden select-none dark:block"
        style={style}
      />
    </span>
  );
}
