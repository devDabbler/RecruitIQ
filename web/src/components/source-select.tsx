"use client";

import { SOURCE_OPTIONS } from "@/lib/sources";
import { cn } from "@/lib/utils";

/**
 * "How did they find us?" (Track 2 Phase 3). One list, in one order, on
 * every way a candidate comes in; values match the API's ApplicationSource.
 */
export function SourceSelect({
  value,
  onChange,
  disabled,
  id,
  className,
}: {
  value: string;
  onChange: (value: string) => void;
  disabled?: boolean;
  id?: string;
  className?: string;
}) {
  return (
    <select
      id={id}
      value={value}
      onChange={(e) => onChange(e.target.value)}
      disabled={disabled}
      aria-label={id ? undefined : "How did they find us?"}
      className={cn(
        "rounded-md border border-slate-200 bg-white px-2 py-2 text-sm text-slate-700",
        className,
      )}
    >
      {SOURCE_OPTIONS.map((option) => (
        <option key={option.value} value={option.value}>
          {option.label}
        </option>
      ))}
    </select>
  );
}
