import type { Metadata } from "next";
import { Suspense } from "react";

import { BlockMapView } from "./BlockMapView";

export const metadata: Metadata = { title: "Block vs Panchayat" };

export default function BlockPage({ params }: { params: { id: string } }) {
  return (
    <Suspense>
      <BlockMapView blockId={Number(params.id)} />
    </Suspense>
  );
}
