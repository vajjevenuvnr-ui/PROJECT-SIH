import type { Metadata } from "next";

import { PanchayatView } from "./PanchayatView";

export const metadata: Metadata = { title: "Panchayat forecast" };

export default function PanchayatPage({ params }: { params: { id: string } }) {
  return <PanchayatView panchayatId={Number(params.id)} />;
}
