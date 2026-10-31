// --- artifact metadata ---
// owner_agent: {{OWNER_AGENT}}
// upstream:    {{UPSTREAM}}
// downstream:  {{DOWNSTREAM}}
// created_at:  {{CREATED_AT}}
// template:    task-scaffolder/component
// ---
import React from "react";

export interface {{NAME}}Props {
  className?: string;
}

export function {{NAME}}({ className }: {{NAME}}Props): React.JSX.Element {
  return (
    <div className={className}>
      {/* implement {{NAME}} */}
    </div>
  );
}

export default {{NAME}};
