import type { Metadata } from "next";

import { ShareIndex } from "./ShareIndex";

export const metadata: Metadata = { title: "Share" };

export default function SharePage() {
  return <ShareIndex />;
}
