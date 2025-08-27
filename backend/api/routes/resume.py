from fastapi import APIRouter, UploadFile, File, HTTPException, Form
from services.ai_assistant import AIAssistant

router = APIRouter()
assistant = AIAssistant()

@router.post("/analyze-resume")
async def analyze_resume(
    job_description: str = Form(...),
    resume: UploadFile = File(...),
):
    try:
        resume_text = (await resume.read()).decode("utf-8")
        analysis = await assistant.analyze_resume_for_job(resume_text, job_description)
        return analysis
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
