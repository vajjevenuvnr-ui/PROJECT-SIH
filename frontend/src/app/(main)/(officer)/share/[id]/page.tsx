import type { Metadata } from "next";

import { ShareView } from "./ShareView";

export const metadata: Metadata = { title: "Share advisory" };

export default function SharePage({ params }: { params: { id: string } }) {
  return <ShareView advisoryId={Number(params.id)} />;
}
