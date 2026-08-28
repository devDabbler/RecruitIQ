import Link from "next/link";

import { CandidateFilters } from "@/components/candidate-filters";
import { EmptyState, ErrorState, PageHeader } from "@/components/page-header";
import { StageBadge } from "@/components/stage-badge";
import { Card } from "@/components/ui/card";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { ApiError } from "@/lib/api";
import { listCandidates } from "@/lib/data";
import { type CandidateSearch, fullName, initials } from "@/lib/domain";

export const dynamic = "force-dynamic";

const PAGE_SIZE = 25;

export default async function CandidatesPage({ searchParams }: PageProps<"/candidates">) {
  const params = await searchParams;
  const keyword = first(params.q);
  const status = first(params.status);
  // A hand-edited `?page=abc` should land on page 1, not send NaN to the API.
  const page = Math.max(1, Number(first(params.page)) || 1);

  let data: CandidateSearch;
  try {
    data = await listCandidates({ keyword, status, page, pageSize: PAGE_SIZE });
  } catch (error) {
    return (
      <>
        <PageHeader title="Candidates" />
        <ErrorState
          title="Could not load candidates"
          detail={error instanceof ApiError ? error.detail : String(error)}
        />
      </>
    );
  }

  const lastPage = Math.max(1, Math.ceil(data.total / PAGE_SIZE));
  const from = data.total === 0 ? 0 : (page - 1) * PAGE_SIZE + 1;
  const to = Math.min(page * PAGE_SIZE, data.total);

  return (
    <>
      <PageHeader
        title="Candidates"
        description={
          data.total === 1 ? "1 candidate" : `${data.total} candidates in the pipeline`
        }
      />

      <CandidateFilters initialKeyword={keyword ?? ""} initialStatus={status ?? ""} />

      {data.results.length === 0 ? (
        <EmptyState
          title="No candidates match those filters"
          detail="Clear the search box or pick a different stage."
        />
      ) : (
        <Card className="overflow-hidden py-0">
          <Table>
            <TableHeader>
              <TableRow className="hover:bg-transparent">
                <TableHead>Name</TableHead>
                <TableHead className="hidden md:table-cell">Current role</TableHead>
                <TableHead className="hidden lg:table-cell">Location</TableHead>
                <TableHead className="hidden xl:table-cell">Skills</TableHead>
                <TableHead className="text-right">Stage</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {data.results.map((candidate) => (
                <TableRow key={candidate.id}>
                  <TableCell>
                    <Link
                      href={`/candidates/${candidate.id}`}
                      className="flex items-center gap-3 font-medium hover:underline"
                    >
                      <span className="grid h-8 w-8 shrink-0 place-items-center rounded-full bg-indigo-50 text-xs font-semibold text-indigo-700">
                        {initials(candidate)}
                      </span>
                      <span className="min-w-0">
                        <span className="block truncate">{fullName(candidate)}</span>
                        <span className="block truncate text-xs font-normal text-slate-500">
                          {candidate.email ?? "No email"}
                        </span>
                      </span>
                    </Link>
                  </TableCell>
                  <TableCell className="hidden max-w-56 truncate text-slate-600 md:table-cell">
                    {candidate.current_position ?? candidate.position_applied ?? "Not listed"}
                    {candidate.current_company ? (
                      <span className="block text-xs text-slate-400">
                        {candidate.current_company}
                      </span>
                    ) : null}
                  </TableCell>
                  <TableCell className="hidden text-slate-600 lg:table-cell">
                    {candidate.location ?? "Not listed"}
                  </TableCell>
                  <TableCell className="hidden xl:table-cell">
                    <SkillChips skills={candidate.skills} />
                  </TableCell>
                  <TableCell className="text-right">
                    <StageBadge status={candidate.status} />
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </Card>
      )}

      {data.total > PAGE_SIZE ? (
        <div className="mt-4 flex items-center justify-between text-sm text-slate-600">
          <span>
            Showing {from}–{to} of {data.total}
          </span>
          <span className="flex gap-2">
            <PageLink params={params} page={page - 1} disabled={page <= 1}>
              Previous
            </PageLink>
            <PageLink params={params} page={page + 1} disabled={page >= lastPage}>
              Next
            </PageLink>
          </span>
        </div>
      ) : null}
    </>
  );
}

/** Next hands repeated query params through as arrays; take the first. */
function first(value: string | string[] | undefined): string | undefined {
  return Array.isArray(value) ? value[0] : value;
}

function SkillChips({ skills }: { skills: string[] | null | undefined }) {
  if (!skills?.length) return <span className="text-xs text-slate-400">None listed</span>;
  return (
    <span className="flex flex-wrap gap-1">
      {skills.slice(0, 3).map((skill) => (
        <span
          key={skill}
          className="rounded bg-slate-100 px-1.5 py-0.5 text-xs text-slate-600"
        >
          {skill}
        </span>
      ))}
      {skills.length > 3 ? (
        <span className="px-1 py-0.5 text-xs text-slate-400">+{skills.length - 3}</span>
      ) : null}
    </span>
  );
}

function PageLink({
  params,
  page,
  disabled,
  children,
}: {
  params: Record<string, string | string[] | undefined>;
  page: number;
  disabled: boolean;
  children: React.ReactNode;
}) {
  if (disabled) {
    return (
      <span className="rounded-md border border-slate-200 px-3 py-1.5 text-slate-300">
        {children}
      </span>
    );
  }

  // Rebuilt from the incoming params so paging preserves the active search and
  // stage filter instead of silently resetting them.
  const query = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    const single = first(value);
    if (key !== "page" && single) query.set(key, single);
  }
  query.set("page", String(page));

  return (
    <Link
      href={`/candidates?${query}`}
      className="rounded-md border border-slate-200 bg-white px-3 py-1.5 font-medium hover:border-slate-300"
    >
      {children}
    </Link>
  );
}
