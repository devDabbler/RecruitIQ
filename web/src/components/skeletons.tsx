/**
 * Shared shapes for the `loading.tsx` files.
 *
 * These exist for a specific reason, not for polish. Every route in this app is
 * `dynamic = "force-dynamic"`, and without a `loading.tsx` boundary Next skips
 * prefetching a dynamic route entirely (see the prefetching guide's static vs.
 * dynamic table). So before these files existed, hovering the nav prefetched
 * nothing and every click paid a full server round trip with a frozen screen.
 *
 * The skeletons therefore need to match the real layout closely enough that the
 * swap is not a second visible jump. Heights below are taken from the
 * components they stand in for, not picked by eye.
 */
import { Skeleton } from "@/components/ui/skeleton";

/**
 * `PageHeader`'s shape, without its content.
 *
 * h-9 is the `text-3xl` title's line box and h-4 the `text-sm` description, so
 * the header keeps its exact height when the real one streams in.
 */
export function HeaderSkeleton({ description = true }: { description?: boolean }) {
  return (
    <div className="mb-6 flex flex-wrap items-end justify-between gap-4">
      <div>
        <Skeleton className="h-9 w-56" />
        {description ? <Skeleton className="mt-2 h-4 w-80 max-w-full" /> : null}
      </div>
    </div>
  );
}

/** A stand-in for a `Card`, matching its rounded-xl corner. */
export function CardSkeleton({ className }: { className?: string }) {
  return <Skeleton className={`w-full rounded-xl ${className ?? "h-32"}`} />;
}

/**
 * `n` card placeholders.
 *
 * Deliberately a fixed count rather than the real one: the real count is only
 * known after the fetch this is standing in for, and guessing high leaves a
 * block of grey that collapses on swap.
 */
export function CardListSkeleton({
  count,
  height = "h-32",
  className,
}: {
  count: number;
  height?: string;
  className?: string;
}) {
  return (
    <div className={className ?? "space-y-3"}>
      {Array.from({ length: count }, (_, i) => (
        <CardSkeleton key={i} className={height} />
      ))}
    </div>
  );
}
