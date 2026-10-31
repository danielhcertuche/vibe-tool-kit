// --- artifact metadata ---
// owner_agent: {{OWNER_AGENT}}
// upstream:    {{UPSTREAM}}
// downstream:  {{DOWNSTREAM}}
// created_at:  {{CREATED_AT}}
// template:    task-scaffolder/dashboard
// ---
import { render } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { {{NAME}}Dashboard } from "./skeleton";

describe("{{NAME}}Dashboard", () => {
  it("renders without crashing", () => {
    render(<{{NAME}}Dashboard />);
    expect(document.querySelector("main")).not.toBeNull();
  });

  it("renders KPI section", () => {
    render(<{{NAME}}Dashboard />);
    expect(document.querySelector('[aria-label="KPIs"]')).not.toBeNull();
  });

  it("renders main chart section", () => {
    render(<{{NAME}}Dashboard />);
    expect(document.querySelector('[aria-label="Main chart"]')).not.toBeNull();
  });
});
