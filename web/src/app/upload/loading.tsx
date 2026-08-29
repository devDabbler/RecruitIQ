import { CardSkeleton, HeaderSkeleton } from "@/components/skeletons";

export default function Loading() {
  return (
    <>
      <HeaderSkeleton />
      <CardSkeleton className="h-64" />
    </>
  );
}
