import { BulkUploader } from "@/components/bulk-uploader";
import { PageHeader } from "@/components/page-header";
import { ResumeUploader, type SelectableJob } from "@/components/resume-uploader";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { listJobs } from "@/lib/data";
import { redirectInterviewer } from "@/lib/guards";
import { CANDIDATES_ADD } from "@/lib/permissions";
import { hasPermission } from "@/lib/session";

export const metadata = { title: "Resume Upload · RecruitIQ" };

export const dynamic = "force-dynamic";

export default async function UploadPage() {
  await redirectInterviewer();
  const writable = await hasPermission(CANDIDATES_ADD);

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
            ? "Parse a resume, review it, then save it straight onto a job's pipeline. Or add several at once."
            : "Extraction runs against a real file you provide. Nothing is written to the database."
        }
      />
      {writable ? (
        <Tabs defaultValue="one">
          <TabsList className="mb-4">
            <TabsTrigger value="one">One resume</TabsTrigger>
            <TabsTrigger value="many">Several resumes</TabsTrigger>
          </TabsList>
          <TabsContent value="one">
            <ResumeUploader canWrite jobs={jobs} />
          </TabsContent>
          <TabsContent value="many">
            <BulkUploader jobs={jobs} />
          </TabsContent>
        </Tabs>
      ) : (
        <ResumeUploader canWrite={false} jobs={jobs} />
      )}
    </>
  );
}
