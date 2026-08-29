import { CardSkeleton, HeaderSkeleton } from "@/components/skeletons";

/**
 * The dashboard is the slowest of the list screens (~390ms server-side) because
 * it fans out to ten API calls. This is what the visitor looks at instead of a
 * frozen previous page while those run.
 */
export default function Loading() {
  return (
    <>
      <HeaderSkeleton />

      <div className="grid gap-4 sm:grid-cols-3">
        <CardSkeleton className="h-24" />
        <CardSkeleton className="h-24" />
        <CardSkeleton className="h-24" />
      </div>

      <div className="mt-6 grid gap-6 lg:grid-cols-2">
        <CardSkeleton className="h-80" />
        <CardSkeleton className="h-80" />
      </div>

      <CardSkeleton className="mt-6 h-72" />
    </>
  );
}
