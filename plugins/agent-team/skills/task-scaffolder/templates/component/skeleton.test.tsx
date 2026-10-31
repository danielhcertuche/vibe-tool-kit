// --- artifact metadata ---
// owner_agent: {{OWNER_AGENT}}
// upstream:    {{UPSTREAM}}
// downstream:  {{DOWNSTREAM}}
// created_at:  {{CREATED_AT}}
// template:    task-scaffolder/component
// ---
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { {{NAME}} } from "./skeleton";

describe("{{NAME}}", () => {
  it("renders without crashing", () => {
    render(<{{NAME}} />);
    expect(document.querySelector("div")).not.toBeNull();
  });

  it("forwards className prop", () => {
    render(<{{NAME}} className="test-class" />);
    expect(document.querySelector(".test-class")).not.toBeNull();
  });
});
