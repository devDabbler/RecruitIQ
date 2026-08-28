import { PageHeader } from "@/components/page-header";
import { ResumeUploader } from "@/components/resume-uploader";
import { canWrite } from "@/lib/session";

export const metadata = { title: "Resume Upload · RecruitIQ" };

export default async function UploadPage() {
  const writable = await canWrite();
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
      <ResumeUploader canWrite={writable} />
    </>
  );
}
