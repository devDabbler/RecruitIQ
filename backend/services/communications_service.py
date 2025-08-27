# backend/services/communications_service.py
import asyncio
import base64
import logging
import os
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
import json

import httpx
from pydantic import BaseModel, Field

from backend.utils.config import Settings
from backend.services.llm_service import LLMService


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
        
        # Generate the email draft using LLaMA
        email_draft = await self.llm_service.generate_text_async(
            prompt=prompt,
            model="llama_70b",  # Use the larger model for better writing quality
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

    async def generate_recruiter_outreach_email(self, role: str) -> str:
        """
        Generate a recruiter outreach email for a specific role.
        
        Args:
            role: The role/position being recruited for
            
        Returns:
            str: The generated email content
        """
        prompt = f"""
        You are a professional recruiter reaching out to potential candidates for a {role} position.
        
        Please draft a compelling outreach email that includes:
        1. A personalized greeting
        2. Brief introduction of your company
        3. Description of the {role} opportunity
        4. Key requirements and benefits
        5. Clear call-to-action
        6. Professional closing
        
        The email should be:
        - Professional but friendly in tone
        - Concise (under 200 words)
        - Specific to the {role} role
        - Include a clear next step for the candidate
        
        Return only the email body text without any additional commentary or formatting.
        """
        
        try:
            email_content = await self.llm_service.generate_text_async(
                prompt=prompt,
                model="llama_70b",  # Use the larger model for better writing quality
                max_tokens=400,
            )
            
            return email_content.strip()
            
        except Exception as e:
            logger.error(f"Error generating recruiter outreach email: {e}")
            # Return a fallback email template
            return f"""
Dear [Candidate Name],

I hope this message finds you well. I'm reaching out because I came across your profile and was impressed by your background in {role}.

We're currently looking for a talented {role} to join our growing team. This is an exciting opportunity to work on cutting-edge projects and make a real impact.

Key requirements for this role include:
- Strong experience in {role}
- Excellent problem-solving skills
- Team collaboration abilities

We offer competitive compensation, great benefits, and a supportive work environment.

Would you be interested in learning more about this opportunity? I'd love to schedule a brief call to discuss the role and see if it might be a good fit for your career goals.

Please let me know if you're interested, and I'll be happy to share more details.

Best regards,
[Your Name]
[Your Title]
[Company Name]
[Contact Information]
            """.strip()