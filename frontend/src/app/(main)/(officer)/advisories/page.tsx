import type { Metadata } from "next";

import { AdvisoriesList } from "./AdvisoriesList";
import { BulkDispatch } from "./BulkDispatch";

export const metadata: Metadata = { title: "Advisories" };

export default function AdvisoriesPage() {
  return (
    <div className="flex flex-col gap-8">
      <BulkDispatch />
      <AdvisoriesList />
    </div>
  );
}
