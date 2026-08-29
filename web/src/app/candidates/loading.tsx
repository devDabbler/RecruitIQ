import { CardSkeleton, HeaderSkeleton } from "@/components/skeletons";
import { Skeleton } from "@/components/ui/skeleton";

/**
 * Also covers paging and filtering, since both are `<Link>`/router navigations
 * into this same segment rather than client-side state.
 */
export default function Loading() {
  return (
    <>
      <HeaderSkeleton />

      {/* CandidateFilters: a search box and a stage select, side by side. */}
      <div className="mb-4 flex flex-wrap gap-2">
        <Skeleton className="h-9 w-full max-w-xs" />
        <Skeleton className="h-9 w-40" />
      </div>

      {/* The table, as one block: its rows are uniform, so a striped skeleton
          would only add motion without adding information. */}
      <CardSkeleton className="h-[32rem]" />
    </>
  );
}
