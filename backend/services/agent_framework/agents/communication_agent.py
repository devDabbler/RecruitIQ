from typing import Any, Dict, List
import logging

from backend.services.agent_framework.base_agent import BaseAgent
from backend.services.agent_framework.agent_registry import register
from backend.services.communications_service import CommunicationsService
from backend.services.llm_service import LLMService

logger = logging.getLogger(__name__)

@register(
    name="CommunicationAgent",
    description="Handles automated and AI-assisted communications with candidates and recruiters."
)
class CommunicationAgent(BaseAgent):
    """Handles candidate and client communications, including email and interview scheduling."""

    def __init__(self, communications_service: CommunicationsService, llm_service: LLMService):
        self.communications_service = communications_service
        self.llm_service = llm_service

    async def execute(self, task: Dict[str, Any], **kwargs) -> Dict[str, Any]:
        action = task.get("action")
        if not action:
            return {"status": "error", "message": "'action' must be specified in the task."}

        logger.info(f"CommunicationAgent executing action: {action}")

        try:
            if action == "send_email":
                return await self._send_email(task)
            elif action == "schedule_interview":
                return await self._schedule_interview(task)
            else:
                return {"status": "error", "message": f"Unknown action: {action}"}
        except Exception as e:
            logger.exception(f"Error executing communication action '{action}': {e}")
            return {"status": "error", "message": str(e)}

    async def _send_email(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Generates and sends an email."""
        recipient = task.get("recipient")
        subject = task.get("subject")
        template = task.get("template")
        context = task.get("context", {})

        if not all([recipient, subject, template]):
            return {"status": "error", "message": "'recipient', 'subject', and 'template' are required for sending email."}

        logger.info(f"Preparing to send email with template '{template}' to {recipient}.")

        # Use LLM to generate email body from template and context
        prompt = f"""
        Generate a professional and engaging email based on the following template and context.
        Template: '{template}'
        Context: {context}
        
        Email Body:
        """
        response_msg = await self.llm_service.generate_text_async(prompt, max_tokens=500)
        body = response_msg.content if hasattr(response_msg, 'content') else str(response_msg)

        # Send the email using the communications service
        result = await self.communications_service.send_email(
            recipient=recipient,
            subject=subject,
            body=body
        )

        return {"status": "completed", "result": result}

    async def _schedule_interview(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Schedules an interview."""
        candidate_email = task.get("candidate_email")
        job_title = task.get("job_title")
        interviewer_emails = task.get("interviewer_emails")
        preferred_times = task.get("preferred_times")

        if not all([candidate_email, job_title, interviewer_emails, preferred_times]):
            return {"status": "error", "message": "'candidate_email', 'job_title', 'interviewer_emails', and 'preferred_times' are required."}

        logger.info(f"Scheduling interview for {candidate_email} for the role of {job_title}.")

        result = await self.communications_service.schedule_interview(
            candidate_email=candidate_email,
            job_title=job_title,
            interviewer_emails=interviewer_emails,
            preferred_times=preferred_times
        )

        return {"status": "completed", "result": result}
