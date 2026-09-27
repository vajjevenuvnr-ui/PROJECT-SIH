import type { Metadata } from "next";

import { AdvisoryView } from "./AdvisoryView";

export const metadata: Metadata = { title: "Crop advisory" };

export default function AdvisoryPage({ params }: { params: { id: string } }) {
  return <AdvisoryView panchayatId={Number(params.id)} />;
}
