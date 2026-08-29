import { CardListSkeleton, HeaderSkeleton } from "@/components/skeletons";
import { Skeleton } from "@/components/ui/skeleton";

/**
 * Distinct from the `<Suspense>` fallback inside `matching/page.tsx`: that one
 * covers re-scoring when the job picker changes, this one covers arriving at
 * the route at all. Without it the ~10s scoring pass had no boundary above it
 * to prefetch against.
 */
export default function Loading() {
  return (
    <>
      <HeaderSkeleton />
      <Skeleton className="h-9 w-72" />
      <CardListSkeleton count={4} className="mt-6 space-y-3" />
    </>
  );
}
