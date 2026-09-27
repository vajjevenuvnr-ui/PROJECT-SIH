import { BadgeCheck, Home, Map, MessageSquareText, Send, ShieldCheck, Users, type LucideIcon } from "lucide-react";

export interface NavItem {
  key: "home" | "blockMap" | "advisories" | "share" | "farmers" | "validation" | "officers";
  icon: LucideIcon;
  /** Build the href; null when it needs a selected block that isn't set. */
  href: (blockId: number | null) => string | null;
  match: (pathname: string) => boolean;
  /** Only shown to admins (sidebar only; admins manage accounts on a desktop). */
  adminOnly?: boolean;
}

export const NAV_ITEMS: NavItem[] = [
  { key: "home", icon: Home, href: () => "/", match: (p) => p === "/" },
  {
    key: "blockMap",
    icon: Map,
    href: (b) => (b ? `/block/${b}` : null),
    match: (p) => p.startsWith("/block") || p.startsWith("/panchayat"),
  },
  { key: "advisories", icon: MessageSquareText, href: () => "/advisories", match: (p) => p.startsWith("/advisories") },
  { key: "share", icon: Send, href: () => "/share", match: (p) => p.startsWith("/share") },
  { key: "farmers", icon: Users, href: () => "/farmers", match: (p) => p.startsWith("/farmers") },
  { key: "validation", icon: BadgeCheck, href: () => "/validation", match: (p) => p.startsWith("/validation") },
  { key: "officers", icon: ShieldCheck, href: () => "/officers", match: (p) => p.startsWith("/officers"), adminOnly: true },
];
