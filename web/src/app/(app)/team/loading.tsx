import { CardSkeleton, HeaderSkeleton } from "@/components/skeletons";

export default function Loading() {
  return (
    <>
      <HeaderSkeleton />
      <div className="grid gap-6 lg:grid-cols-3">
        <CardSkeleton className="h-96 lg:col-span-2" />
        <CardSkeleton className="h-96" />
      </div>
    </>
  );
}
