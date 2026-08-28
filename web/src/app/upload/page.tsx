import { PageHeader } from "@/components/page-header";
import { ResumeUploader } from "@/components/resume-uploader";

export const metadata = { title: "Resume Upload · RecruitIQ" };

export default function UploadPage() {
  return (
    <>
      <PageHeader
        title="Resume Upload"
        description="Extraction runs against a real file you provide. Nothing is written to the database."
      />
      <ResumeUploader />
    </>
  );
}
