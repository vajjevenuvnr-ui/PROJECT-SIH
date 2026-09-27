import type { Metadata } from "next";

import { FarmersView } from "./FarmersView";

export const metadata: Metadata = { title: "Farmers" };

export default function FarmersPage() {
  return <FarmersView />;
}
