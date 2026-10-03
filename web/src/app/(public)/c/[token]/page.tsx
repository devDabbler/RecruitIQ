import { PublicStatusView } from "@/components/public-status-view";
import { getPublicStatus } from "@/lib/data";
import { looksLikeToken } from "@/lib/public-status";

export const dynamic = "force-dynamic";

export default async function CandidateStatusPage({ params }: PageProps<"/c/[token]">) {
  const { token } = await params;
  const status = looksLikeToken(token) ? await getPublicStatus(token).catch(() => null) : null;

  if (!status) {
    return (
      <div className="space-y-3 py-16 text-center">
        <h1 className="text-xl font-semibold tracking-tight text-slate-900">
          This link is not active
        </h1>
        <p className="mx-auto max-w-md text-sm text-slate-600">
          It may have been replaced by a newer link. Ask the person who sent it to you for a fresh
          one.
        </p>
      </div>
    );
  }

  return <PublicStatusView status={status} />;
}
