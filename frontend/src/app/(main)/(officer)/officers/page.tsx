import type { Metadata } from "next";

import { OfficersView } from "./OfficersView";

export const metadata: Metadata = { title: "Officers" };

export default function OfficersPage() {
  return <OfficersView />;
}
