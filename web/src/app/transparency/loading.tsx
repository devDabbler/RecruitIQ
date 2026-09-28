import { CardListSkeleton, HeaderSkeleton } from "@/components/skeletons";

export default function Loading() {
  return (
    <>
      <HeaderSkeleton />
      <CardListSkeleton count={3} className="space-y-4" />
    </>
  );
}
