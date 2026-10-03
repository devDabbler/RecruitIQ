import { CardSkeleton, HeaderSkeleton } from "@/components/skeletons";
import { Skeleton } from "@/components/ui/skeleton";

/**
 * The highest-traffic navigation in the app: every candidate row and every
 * match result links here. Mirrors the 1/2 column split of the real page.
 */
export default function Loading() {
  return (
    <>
      {/* The "All candidates" back link, which is present before any data. */}
      <Skeleton className="mb-4 h-5 w-32" />
      <HeaderSkeleton />

      <div className="grid gap-6 lg:grid-cols-3">
        <div className="space-y-6 lg:col-span-1">
          <CardSkeleton className="h-72" />
          <CardSkeleton className="h-40" />
        </div>
        <div className="space-y-6 lg:col-span-2">
          <CardSkeleton className="h-64" />
          <div className="grid gap-6 md:grid-cols-2">
            <CardSkeleton className="h-40" />
            <CardSkeleton className="h-40" />
          </div>
        </div>
      </div>
    </>
  );
}
