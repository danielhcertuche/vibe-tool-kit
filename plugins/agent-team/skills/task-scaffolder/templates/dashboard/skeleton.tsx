// --- artifact metadata ---
// owner_agent: {{OWNER_AGENT}}
// upstream:    {{UPSTREAM}}
// downstream:  {{DOWNSTREAM}}
// created_at:  {{CREATED_AT}}
// template:    task-scaffolder/dashboard
// ---
import React from "react";

export interface {{NAME}}DashboardProps {
  className?: string;
}

export function {{NAME}}Dashboard({
  className,
}: {{NAME}}DashboardProps): React.JSX.Element {
  return (
    <main className={className} style={{ display: "grid", gap: "1rem" }}>
      {/* KPI row */}
      <section aria-label="KPIs" style={{ display: "flex", gap: "1rem" }}>
        <div className="kpi-card">{/* KPI 1 */}</div>
        <div className="kpi-card">{/* KPI 2 */}</div>
        <div className="kpi-card">{/* KPI 3 */}</div>
      </section>

      {/* Main chart */}
      <section aria-label="Main chart">
        {/* TODO: add chart from {{UPSTREAM}} */}
      </section>

      {/* Detail table */}
      <section aria-label="Detail table">
        {/* TODO: add data table */}
      </section>
    </main>
  );
}

export default {{NAME}}Dashboard;
