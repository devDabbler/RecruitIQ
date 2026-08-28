"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { useEffect, useState, useTransition } from "react";
import { Search } from "lucide-react";

import { Input } from "@/components/ui/input";
import { PIPELINE_STAGES, STAGE_LABELS } from "@/lib/domain";
import { cn } from "@/lib/utils";

/**
 * Search-as-you-type over the candidate list.
 *
 * Pushes the query into the URL and lets the Server Component re-render, rather
 * than holding a second copy of the list on the client. That keeps one source
 * of truth and makes every filtered view linkable.
 */
export function CandidateFilters({
  initialKeyword,
  initialStatus,
}: {
  initialKeyword: string;
  initialStatus: string;
}) {
  const router = useRouter();
  const params = useSearchParams();
  const [keyword, setKeyword] = useState(initialKeyword);
  const [pending, startTransition] = useTransition();

  useEffect(() => {
    // Debounced: a keystroke per request would hammer the API and race its own
    // responses. 300ms is below the threshold where typing feels laggy.
    const timer = setTimeout(() => {
      const next = new URLSearchParams(params.toString());
      if (keyword) next.set("q", keyword);
      else next.delete("q");
      next.delete("page");
      if (next.toString() !== params.toString()) {
        startTransition(() => router.replace(`/candidates?${next}`, { scroll: false }));
      }
    }, 300);
    return () => clearTimeout(timer);
    // `params` is intentionally read fresh inside the timer, not tracked here:
    // adding it re-arms the debounce on every navigation this effect causes.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [keyword]);

  function setStatus(status: string) {
    const next = new URLSearchParams(params.toString());
    if (status) next.set("status", status);
    else next.delete("status");
    next.delete("page");
    startTransition(() => router.replace(`/candidates?${next}`, { scroll: false }));
  }

  return (
    <div className="mb-4 space-y-3">
      <div className="relative max-w-md">
        <Search className="absolute top-2.5 left-3 h-4 w-4 text-slate-400" aria-hidden />
        <Input
          value={keyword}
          onChange={(e) => setKeyword(e.target.value)}
          placeholder="Search by name, skill, or position…"
          aria-label="Search candidates"
          className={cn("pl-9", pending && "opacity-70")}
        />
      </div>

      <div className="flex flex-wrap gap-2">
        <FilterChip active={!initialStatus} onClick={() => setStatus("")}>
          All
        </FilterChip>
        {PIPELINE_STAGES.map((stage) => (
          <FilterChip
            key={stage}
            active={initialStatus === stage}
            onClick={() => setStatus(stage)}
          >
            {STAGE_LABELS[stage]}
          </FilterChip>
        ))}
      </div>
    </div>
  );
}

function FilterChip({
  active,
  onClick,
  children,
}: {
  active: boolean;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={active}
      className={cn(
        "rounded-full border px-3 py-1 text-xs font-medium transition-colors",
        active
          ? "border-slate-900 bg-slate-900 text-white"
          : "border-slate-200 bg-white text-slate-600 hover:border-slate-300 hover:text-slate-900",
      )}
    >
      {children}
    </button>
  );
}
