import type { Metadata } from "next";

import { FarmerReports } from "./FarmerReports";
import { ValidationView } from "./ValidationView";

export const metadata: Metadata = { title: "Validation" };

export default function ValidationPage() {
  return (
    <div className="flex flex-col gap-6">
      <ValidationView />
      <FarmerReports />
    </div>
  );
}
