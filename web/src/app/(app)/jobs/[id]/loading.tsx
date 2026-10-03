import { CardSkeleton, HeaderSkeleton } from "@/components/skeletons";
import { Skeleton } from "@/components/ui/skeleton";

/** Mirrors the 2/1 column split of the real job detail page. */
export default function Loading() {
  return (
    <>
      <Skeleton className="mb-4 h-5 w-24" />
      <HeaderSkeleton />

      <div className="grid gap-6 lg:grid-cols-3">
        <div className="space-y-6 lg:col-span-2">
          <CardSkeleton className="h-40" />
          <CardSkeleton className="h-40" />
          <CardSkeleton className="h-64" />
        </div>
        <div className="space-y-6">
          <CardSkeleton className="h-72" />
        </div>
      </div>
    </>
  );
}
