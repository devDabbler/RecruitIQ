import { CardListSkeleton, HeaderSkeleton } from "@/components/skeletons";

export default function Loading() {
  return (
    <>
      <HeaderSkeleton />
      <CardListSkeleton
        count={6}
        height="h-56"
        className="grid gap-4 md:grid-cols-2 xl:grid-cols-3"
      />
    </>
  );
}
