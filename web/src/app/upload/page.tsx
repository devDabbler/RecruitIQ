import { PageHeader } from "@/components/page-header";
import { ResumeUploader, type SelectableJob } from "@/components/resume-uploader";
import { listJobs } from "@/lib/data";
import { canWrite } from "@/lib/session";

export const metadata = { title: "Resume Upload · RecruitIQ" };

export const dynamic = "force-dynamic";

export default async function UploadPage() {
  const writable = await canWrite();

  // Scoring against a real requisition is the better path, but it is not worth
  // taking the upload screen down for: if the list cannot be fetched the
  // uploader falls back to a free-text role.
  let jobs: SelectableJob[] = [];
  try {
    const list = await listJobs();
    jobs = list.results
      .map((job) => ({
        id: job.id,
        title: job.title,
        department: job.department,
        status: job.status,
      }))
      // Open roles first, then alphabetical, matching the jobs page.
      .sort((a, b) => {
        if ((a.status === "open") !== (b.status === "open")) return a.status === "open" ? -1 : 1;
        return a.title.localeCompare(b.title);
      });
  } catch {
    jobs = [];
  }

  return (
    <>
      <PageHeader
        title="Resume Upload"
        description={
          writable
            ? "Parse a resume, review the extraction and fit, then save it to the pipeline."
            : "Extraction runs against a real file you provide. Nothing is written to the database."
        }
      />
      <ResumeUploader canWrite={writable} jobs={jobs} />
    </>
  );
}
