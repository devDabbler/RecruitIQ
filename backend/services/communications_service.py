# backend/services/communications_service.py
import asyncio
import base64
import logging
import os
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
import json
import re

import httpx
from pydantic import BaseModel, Field

from backend.utils.config import Settings
from backend.services.llm_service import LLMService
from backend.utils.text_sanitizer import clean_generated_text


logger = logging.getLogger(__name__)


class EmailMessage(BaseModel):
    """Model for email messages."""
    id: str
    subject: str
    sender: str
    recipients: List[str]
    cc: Optional[List[str]] = None
    bcc: Optional[List[str]] = None
    body: str
    html_body: Optional[str] = None
    timestamp: datetime
    thread_id: Optional[str] = None
    is_read: bool = False
    labels: List[str] = Field(default_factory=list)
    attachments: List[Dict[str, Any]] = Field(default_factory=list)


class EmailThread(BaseModel):
    """Model for email threads."""
    thread_id: str
    subject: str
    participants: List[str]
    messages: List[EmailMessage]
    latest_timestamp: datetime
    is_read: bool = False
    labels: List[str] = Field(default_factory=list)


class CommunicationsService:
    def __init__(
        self,
        settings: Settings,
        llm_service: LLMService,
    ):
        self.settings = settings
        self.llm_service = llm_service
        
        # Setup HTTP client for API calls
        self.http_client = httpx.AsyncClient(timeout=30.0)
        
        # Initialize OAuth credentials
        self.token = None
        self.token_expiry = None
    
    async def close(self):
        """Close the HTTP client when service is shut down."""
        await self.http_client.aclose()
    
    async def authenticate_outlook(self):
        """Authenticate with Microsoft Graph API for Outlook access."""
        # In a real implementation, you would use OAuth flow
        # For POC purposes, simulate a successful auth
        self.token = "simulated_token"
        self.token_expiry = time.time() + 3600  # 1 hour expiry
        
        return True
    
    async def get_recent_emails(self, count: int = 20) -> List[EmailMessage]:
        """Get recent emails from the connected account."""
        # Ensure we're authenticated
        if not self.token or time.time() > self.token_expiry:
            await self.authenticate_outlook()
        
        # In a real implementation, you would call the Microsoft Graph API
        # For POC purposes, generate simulated emails
        emails = []
        
        for i in range(count):
            # Create a simulated email
            email = EmailMessage(
                id=f"email_{i}",
                subject=f"Simulated Email {i}",
                sender=f"sender{i}@example.com",
                recipients=["recruiter@yourcompany.com"],
                body=f"This is the body of simulated email {i}.",
                html_body=f"<p>This is the <b>HTML body</b> of simulated email {i}.</p>",
                timestamp=datetime.now() - timedelta(hours=i),
                thread_id=f"thread_{i % 5}",  # Group into 5 threads
                is_read=bool(i % 3),  # Mix of read/unread
                labels=["Inbox"] + (["Candidate"] if i % 4 == 0 else []),
            )
            
            emails.append(email)
        
        return emails
    
    async def group_emails_into_threads(self, emails: List[EmailMessage]) -> List[EmailThread]:
        """Group individual emails into conversation threads."""
        thread_map = {}
        
        for email in emails:
            thread_id = email.thread_id or email.id  # Use email ID if no thread ID
            
            if thread_id not in thread_map:
                # Create new thread
                thread_map[thread_id] = EmailThread(
                    thread_id=thread_id,
                    subject=email.subject,
                    participants=[email.sender] + email.recipients,
                    messages=[email],
                    latest_timestamp=email.timestamp,
                    is_read=email.is_read,
                    labels=email.labels.copy(),
                )
            else:
                # Add to existing thread
                thread = thread_map[thread_id]
                thread.messages.append(email)
                
                # Update thread metadata
                if email.timestamp > thread.latest_timestamp:
                    thread.latest_timestamp = email.timestamp
                
                # Update participant list
                for participant in [email.sender] + email.recipients:
                    if participant not in thread.participants:
                        thread.participants.append(participant)
                
                # Thread is read only if all messages are read
                thread.is_read = thread.is_read and email.is_read
                
                # Merge labels
                for label in email.labels:
                    if label not in thread.labels:
                        thread.labels.append(label)
        
        # Sort threads by latest message time
        threads = list(thread_map.values())
        threads.sort(key=lambda t: t.latest_timestamp, reverse=True)
        
        return threads
    
    async def draft_email_response(
        self, 
        thread: EmailThread, 
        context: Optional[Dict[str, Any]] = None
    ) -> str:
        """Draft an appropriate email response based on thread context."""
        # Extract the latest message and thread context
        latest_message = max(thread.messages, key=lambda m: m.timestamp)
        
        # Format conversation history
        conversation = "\n\n".join([
            f"From: {msg.sender}\nTime: {msg.timestamp}\nMessage: {msg.body}"
            for msg in sorted(thread.messages, key=lambda m: m.timestamp)
        ])
        
        # Add recruiting context if available
        context_text = ""
        if context:
            if "candidate" in context:
                candidate = context["candidate"]
                context_text += f"\nCandidate: {candidate.get('name')}\n"
                context_text += f"Role: {context.get('job_title', 'Not specified')}\n"
                context_text += f"Status: {context.get('status', 'Not specified')}\n"
                
                if "notes" in context:
                    context_text += f"Notes: {context['notes']}\n"
        
        # Build the prompt
        prompt = f"""
        You are a professional recruiter. Draft an email response to the following conversation thread.
        
        Conversation history:
        {conversation}
        
        {context_text}
        
        Please draft a professional and appropriate response email. The tone should be friendly but professional.
        Focus on being helpful, concise, and action-oriented.
        
        Return only the email body text without any additional commentary.
        """
        
        # Generate the email draft using available model
        email_draft = await self.llm_service.generate_text_async(
            prompt=prompt,
            model="meta-llama/llama-3.3-8b-instruct:free",  # Use available model for better writing quality
            max_tokens=500,
        )
        
        return email_draft.strip()
    
    async def schedule_interview(
        self,
        candidate_email: str,
        job_title: str,
        interviewer_emails: List[str],
        preferred_times: List[Dict[str, Any]],
        duration_minutes: int = 60,
        location: str = "Zoom",
    ) -> Dict[str, Any]:
        """Schedule an interview with the candidate and interviewers."""
        # In a real implementation, you would:
        # 1. Check availability of interviewers
        # 2. Create a calendar event
        # 3. Generate a Zoom link
        # 4. Send invitations
        
        # For POC purposes, simulate a successful scheduling
        interview_time = preferred_times[0] if preferred_times else {
            "start": datetime.now() + timedelta(days=3, hours=10),
            "end": datetime.now() + timedelta(days=3, hours=11),
        }
        
        zoom_link = "https://zoom.us/j/123456789?pwd=abcdefghijklmnopqrstuvwxyz"
        
        # Generate meeting details
        meeting = {
            "id": f"meeting_{int(time.time())}",
            "subject": f"Interview: {job_title}",
            "start_time": interview_time["start"],
            "end_time": interview_time["end"],
            "attendees": [candidate_email] + interviewer_emails,
            "location": location,
            "online_meeting_link": zoom_link,
            "status": "confirmed",
        }
        
        return meeting

    async def generate_recruiter_outreach_email(
        self,
        role: str,
        tone: Optional[str] = None,
        creativity: Optional[str] = None,
        subject_line_count: int = 3,
        job_data: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Generate a recruiter outreach email for a specific role with style controls.

        Args:
            role: The role/position being recruited for
            tone: Desired tone, e.g., "professional", "warm", "enthusiastic", "direct", "playful"
            creativity: Creativity level, e.g., "low", "medium", "high"
            subject_line_count: Number of subject line options to produce

        Returns:
            Dict with keys: {"body": str, "subject_lines": List[str]}
        """
        # Map tone/creativity into prompt guidance
        tone = (tone or "professional, warm").strip()
        creativity = (creativity or "medium").strip().lower()
        creativity_map = {
            "low": "focus on clarity and straightforward wording; avoid metaphors and marketing fluff",
            "medium": "balanced creativity with professional tone; light persuasive language",
            "high": "more expressive and catchy phrasing while staying professional",
        }
        creativity_hint = creativity_map.get(creativity, creativity_map["medium"])

        # Build optional job context to ground the outreach copy
        job_context = ""
        try:
            if isinstance(job_data, dict) and job_data:
                title = job_data.get("title") or role
                department = job_data.get("department")
                location = job_data.get("location") or job_data.get("location_city")
                location_type = job_data.get("location_type")
                job_type = job_data.get("job_type")
                experience_level = job_data.get("experience_level")
                overview = job_data.get("job_overview") or job_data.get("description")
                reqs = job_data.get("required_qualifications") or job_data.get("requirements")
                skills = job_data.get("skills")
                if isinstance(skills, list):
                    skills = ", ".join([str(s) for s in skills if str(s).strip()])

                lines = [
                    f"title: {title}" if title else "",
                    f"department: {department}" if department else "",
                    f"location: {location}" if location else "",
                    f"location_type: {location_type}" if location_type else "",
                    f"job_type: {job_type}" if job_type else "",
                    f"experience_level: {experience_level}" if experience_level else "",
                    f"overview: {overview}" if overview else "",
                    f"required_qualifications: {reqs}" if reqs else "",
                    f"skills: {skills}" if skills else "",
                ]
                job_context = "\n".join([ln for ln in lines if ln])
        except Exception:
            # Fail open: if anything goes wrong, just skip job context
            job_context = ""

        prompt_job_ctx = (
            f"Ground the message in the following job context. Do not invent details not present here.\n\n"
            f"JOB CONTEXT:\n{job_context}\n\n" if job_context else ""
        )

        prompt = f"""
        You are a recruiter writing outreach to an individual candidate for a {role} role.

        Requirements:
        - Address the candidate directly (e.g., "Hi [Candidate Name],"). Do NOT write to a hiring manager.
        - Style tone: {tone}.
        - Creativity level: {creativity} ({creativity_hint})
        - Length: under 180–200 words.
        - Use candidate-centric language (you/your).
        - USE PLACEHOLDERS for sender/company identity. Never invent real names or companies.
          Use exactly these placeholders when referring to yourself or the company:
          [Your Name], [Your Title], [Company Name], [Company Website] (optional)

        {prompt_job_ctx}

        IMPORTANT: Return ONLY a valid JSON object with this exact structure:
        {{
          "subject_lines": ["Subject 1", "Subject 2", "Subject 3"],
          "body": "Complete email body text here"
        }}

        The body should include (in this order with clean spacing):
        - Greeting line with the placeholder: Hi [Candidate Name],
        - 1 blank line, then a short intro using placeholders for your identity/company
        - A concise paragraph about the {role} opportunity grounded in job context if provided
        - A short bullet list (2–4 items) using "- " dashes (not asterisks)
        - Clear call to action to chat or apply
        - Signature block using placeholders on separate lines:
          Best regards,\n[Your Name]\n[Your Title]\n[Company Name]\n[Company Website]

        Do NOT include any text outside the JSON object. Do NOT use markdown formatting or code fences.
        """

        try:
            raw = await self.llm_service.generate_text_async(
                prompt=prompt,
                model="meta-llama/llama-3.3-8b-instruct:free",
                max_tokens=500,
            )

            # Extract JSON from possible fencing
            json_text = raw.strip()
            fence_match = re.search(r"```(?:json)?\s*(.*?)```", json_text, re.DOTALL)
            if fence_match:
                json_text = fence_match.group(1).strip()

            data: Dict[str, Any]
            try:
                data = json.loads(json_text)
            except Exception as e:
                logger.warning(f"Failed to parse JSON from AI response: {e}")
                logger.warning(f"Raw response: {json_text[:200]}...")
                
                # Fallback: try to extract structured data from the response
                # Look for subject lines and body patterns
                subject_lines = []
                body = ""
                
                # Try to find subject lines in the text
                subject_match = re.search(r'"subject_lines":\s*\[(.*?)\]', json_text, re.DOTALL)
                if subject_match:
                    subject_text = subject_match.group(1)
                    # Extract individual subject lines
                    subjects = re.findall(r'"([^"]+)"', subject_text)
                    subject_lines = [s.strip() for s in subjects if s.strip()][:subject_line_count]
                
                # Try to find body content
                body_match = re.search(r'"body":\s*"([^"]*(?:\\.[^"]*)*)"', json_text, re.DOTALL)
                if body_match:
                    body = body_match.group(1)
                    # Unescape JSON string
                    body = body.replace('\\n', '\n').replace('\\"', '"').replace('\\t', '\t')
                else:
                    # If no structured data found, use the raw text as body
                    body = json_text
                
                data = {"subject_lines": subject_lines, "body": body}

            # Validate structure
            subject_lines = data.get("subject_lines") or []
            if not isinstance(subject_lines, list):
                subject_lines = []
            subject_lines = [str(s).strip() for s in subject_lines if str(s).strip()][:subject_line_count]

            body = data.get("body") or ""
            body = str(body).strip()

            # --- Formatting & placeholder normalization helpers ---
            def _normalize_placeholders(text: str) -> str:
                t = text.replace("\r\n", "\n").replace("\r", "\n").strip()

                # Ensure greeting
                if not re.match(r"(?i)\s*(hi|hello|dear)\s*\[candidate name\]", t):
                    t = "Hi [Candidate Name],\n\n" + t

                # Replace any invented sender/company with placeholders
                # Common intro patterns
                t = re.sub(r"(?i)\bi'm\s+([A-Z][A-Za-z\-']+(?:\s+[A-Z][A-Za-z\-']+)*)\b", "I'm [Your Name]", t)
                t = re.sub(r"(?i)\bi am\s+([A-Z][A-Za-z\-']+(?:\s+[A-Z][A-Za-z\-']+)*)\b", "I am [Your Name]", t)
                t = re.sub(r"(?i)\bwith\s+([A-Z][\w .,&-]+)\b", "with [Company Name]", t)
                t = re.sub(r"(?i)\bat\s+([A-Z][\w .,&-]+)\b", "at [Company Name]", t)

                # If title is stated generically (e.g., a recruiter), leave it; otherwise allow placeholder
                t = re.sub(r"(?i)\b(as|working as)\s+([\w\- ]{2,40})\s+at\s+\[Company Name\]", r"as [Your Title] at [Company Name]", t)

                # Normalize bullet markers to '- ' (no extra blank lines between bullets)
                raw_lines = t.split('\n')
                normalized_lines = []
                for ln in raw_lines:
                    if re.match(r"^\s*[\*•]\s+", ln):
                        ln = re.sub(r"^\s*[\*•]\s+", "- ", ln)
                    normalized_lines.append(ln.rstrip())

                # Compact whitespace: allow max one blank line between paragraphs
                compact_lines = []
                previous_blank = False
                in_bullets = False
                for ln in normalized_lines:
                    is_bullet = bool(re.match(r"^\s*-\s+", ln))
                    is_blank = (ln.strip() == "")

                    if is_bullet:
                        # Start of bullet block: ensure exactly one blank line before it
                        if not in_bullets:
                            if compact_lines and compact_lines[-1].strip() != "":
                                compact_lines.append("")
                        in_bullets = True
                        compact_lines.append(ln)
                        previous_blank = False
                        continue

                    # Blank lines inside a bullet block are skipped entirely
                    if is_blank and in_bullets:
                        continue

                    # Non-bullet line
                    if is_blank:
                        if not previous_blank and compact_lines:
                            compact_lines.append("")
                        previous_blank = True
                    else:
                        compact_lines.append(ln)
                        previous_blank = False
                        in_bullets = False

                t = "\n".join(compact_lines).strip()

                # Enforce signature block placeholders
                if re.search(r"(?i)\bbest\s+regards\b", t) or re.search(r"(?i)\bthanks\b", t):
                    # Replace any trailing name/title/company lines with placeholders
                    t = re.sub(
                        r"(?is)(best\s+regards,?\s*)(?:.*?)(?:\n\s*)*$",
                        "Best regards,\n[Your Name]\n[Your Title]\n[Company Name]\n[Company Website]",
                        t.strip(),
                    )
                else:
                    t = t.rstrip() + "\n\nBest regards,\n[Your Name]\n[Your Title]\n[Company Name]\n[Company Website]"

                # Collapse 3+ blank lines to max 2
                t = re.sub(r"\n{3,}", "\n\n", t)
                return t.strip()

            # Post-generation guardrails: ensure candidate-facing greeting and placeholders
            lowered = body.lower()
            if "dear hiring manager" in lowered or "hiring manager" in lowered:
                body = re.sub(r"(?i)dear\s*hiring\s*manager\s*,?", "Hi [Candidate Name],", body)
                body = body.replace("hiring manager", "candidate")
            body = _normalize_placeholders(body)

            # Final sanitization to remove any trailing placeholder headings
            body = clean_generated_text(body)

            return {"body": body, "subject_lines": subject_lines}

        except Exception as e:
            logger.error(f"Error generating recruiter outreach email: {e}")
            # Fallback template with simple subject lines
            fallback_body = f"""
Hi [Candidate Name],

I came across your background in {role} and think you could be a great fit for an opening on our team. We’re building impactful products and looking for someone who can contribute quickly.

What you’ll do / bring:
- Apply your {role} expertise to solve real customer problems
- Collaborate with a supportive, high-ownership team
- Grow in a role with visibility and impact

If you’re open to a quick chat, I’d love to share more and learn about what you’re looking for next.

Best,
[Your Name]
[Your Title]
[Company]
            """.strip()
            return {
                "body": fallback_body,
                "subject_lines": [
                    f"Opportunity for {role}",
                    f"Quick chat about a {role} role?",
                    f"Your {role} experience stood out",
                ],
            }