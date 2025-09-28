import imaplib
import email
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import smtplib
from typing import Type, List, Dict, Any
from pydantic import BaseModel, Field
from crewai.tools import BaseTool
import os
from datetime import datetime
import json
import re

class EmailConnectionInput(BaseModel):
    email_address: str = Field(..., description="Email address to connect to")
    password: str = Field(..., description="Email password or app password")
    imap_server: str = Field(default="", description="IMAP server (e.g., imap.gmail.com)")
    smtp_server: str = Field(default="", description="SMTP server (e.g., smtp.gmail.com)")

class EmailScanInput(BaseModel):
    folder: str = Field(default="INBOX", description="Email folder to scan")
    limit: int = Field(default=10, description="Number of recent emails to fetch")
    unread_only: bool = Field(default=True, description="Only fetch unread emails")

class EmailInboxScanner(BaseTool):
    name: str = "email_inbox_scanner"
    description: str = "Scan email inbox for recent emails and extract content automatically"
    args_schema: Type[BaseModel] = EmailScanInput
    
    def _run(self, folder: str = "INBOX", limit: int = 10, unread_only: bool = True) -> str:
        """Scan inbox and return recent emails"""
        try:
            # Get email credentials from environment
            email_address = os.getenv('EMAIL_ADDRESS')
            email_password = os.getenv('EMAIL_PASSWORD')  # App password for Gmail
            imap_server = os.getenv('IMAP_SERVER', 'imap.gmail.com')
            
            if not email_address or not email_password:
                return json.dumps({
                    "error": "Email credentials not configured",
                    "setup_instructions": {
                        "gmail": {
                            "1": "Enable 2-factor authentication",
                            "2": "Generate app password: https://myaccount.google.com/apppasswords",
                            "3": "Set environment variables: EMAIL_ADDRESS, EMAIL_PASSWORD, IMAP_SERVER"
                        },
                        "outlook": {
                            "imap_server": "outlook.office365.com",
                            "smtp_server": "smtp.office365.com"
                        }
                    }
                })
            
            # Connect to IMAP server
            mail = imaplib.IMAP4_SSL(imap_server)
            mail.login(email_address, email_password)
            mail.select(folder)
            
            # Search for emails
            search_criteria = 'UNSEEN' if unread_only else 'ALL'
            status, messages = mail.search(None, search_criteria)
            
            if status != 'OK':
                return json.dumps({"error": "Failed to search emails"})
            
            email_ids = messages[0].split()
            recent_emails = []
            
            # Process recent emails (limit the number)
            for email_id in email_ids[-limit:]:
                status, msg_data = mail.fetch(email_id, '(RFC822)')
                if status != 'OK':
                    continue
                    
                for response_part in msg_data:
                    if isinstance(response_part, tuple):
                        email_message = email.message_from_bytes(response_part[1])
                        
                        # Extract email details
                        subject = email_message['Subject'] or "No Subject"
                        sender = email_message['From'] or "Unknown Sender"
                        date = email_message['Date'] or "Unknown Date"
                        
                        # Get email body
                        body = self._extract_email_body(email_message)
                        
                        # Clean and extract key information
                        cleaned_body = self._clean_email_content(body)
                        
                        recent_emails.append({
                            "id": email_id.decode(),
                            "subject": subject,
                            "sender": sender,
                            "date": date,
                            "body": cleaned_body[:1000],  # Limit body length
                            "full_body": body,
                            "priority_indicators": self._detect_priority_indicators(subject, body),
                            "auto_analysis_ready": True
                        })
            
            mail.logout()
            
            result = {
                "status": "success",
                "folder": folder,
                "total_found": len(email_ids),
                "returned": len(recent_emails),
                "emails": recent_emails,
                "suggestions": {
                    "high_priority": [email for email in recent_emails if email["priority_indicators"]["urgency_score"] > 70],
                    "buying_intent": [email for email in recent_emails if email["priority_indicators"]["buying_intent"] > 60]
                }
            }
            
            return json.dumps(result, indent=2)
            
        except Exception as e:
            return json.dumps({
                "error": f"Failed to scan inbox: {str(e)}",
                "troubleshooting": {
                    "gmail": "Make sure to use App Password, not regular password",
                    "2fa": "Two-factor authentication must be enabled for Gmail",
                    "less_secure": "Gmail no longer supports 'less secure apps'"
                }
            })
    
    def _extract_email_body(self, email_message) -> str:
        """Extract text content from email message"""
        body = ""
        
        if email_message.is_multipart():
            for part in email_message.walk():
                content_type = part.get_content_type()
                content_disposition = str(part.get("Content-Disposition", ""))
                
                if content_type == "text/plain" and "attachment" not in content_disposition:
                    try:
                        body += part.get_payload(decode=True).decode('utf-8', errors='ignore')
                    except:
                        body += str(part.get_payload())
        else:
            try:
                body = email_message.get_payload(decode=True).decode('utf-8', errors='ignore')
            except:
                body = str(email_message.get_payload())
        
        return body
    
    def _clean_email_content(self, body: str) -> str:
        """Clean email content for analysis"""
        # Remove email signatures
        lines = body.split('\n')
        cleaned_lines = []
        
        signature_indicators = ['--', 'sent from', 'best regards', 'sincerely', 'thank you']
        
        for line in lines:
            line_lower = line.lower().strip()
            # Stop at common signature indicators
            if any(indicator in line_lower for indicator in signature_indicators) and len(line.strip()) < 50:
                break
            cleaned_lines.append(line)
        
        cleaned_body = '\n'.join(cleaned_lines)
        
        # Remove quoted text (replies)
        if '>' in cleaned_body:
            lines = cleaned_body.split('\n')
            non_quoted = [line for line in lines if not line.strip().startswith('>')]
            cleaned_body = '\n'.join(non_quoted)
        
        return cleaned_body.strip()
    
    def _detect_priority_indicators(self, subject: str, body: str) -> Dict[str, Any]:
        """Detect priority and intent indicators"""
        # Normalize text: combine subject + content and clean it
        raw_text = f"{subject} {body}"
        text = raw_text.lower()
        # Replace underscores and other separators with spaces for better matching
        text = text.replace('_', ' ').replace('-', ' ').replace('.', ' ')
        
        # Professional/Important indicators (HIGH PRIORITY)
        professional_keywords = [
            'github', 'linkedin', 'job', 'hiring', 'interview', 'career',
            'invitation', 'collaborate', 'pull request', 'repository', 'organization',
            'team', 'project', 'developer', 'engineer', 'opportunity', 'position',
            'goldman sachs', 'microsoft', 'google', 'amazon', 'apple', 'facebook',
            'software engineer', 'hackathon', 'hackathons', 'devpost', 'coding',
            'programming', 'technical', 'startup', 'internship', 'full time',
            'part time', 'remote', 'work from home', 'salary', 'benefits',
            'recruiter', 'hr', 'human resources', 'talent', 'application'
        ]
        professional_score = sum(20 for word in professional_keywords if word in text)
        
        # Urgency indicators
        urgency_words = ['urgent', 'asap', 'immediately', 'rush', 'deadline', 'today', 'this week']
        urgency_score = sum(5 for word in urgency_words if word in text)
        
        # Buying intent indicators
        buying_words = ['demo', 'pricing', 'price', 'purchase', 'buy', 'contract', 'solution', 'budget', 'timeline']
        buying_intent = sum(10 for word in buying_words if word in text)
        
        # Business indicators
        business_words = ['meeting', 'call', 'discuss', 'schedule', 'decision', 'interested', 'evaluation']
        business_score = sum(3 for word in business_words if word in text)
        
        # Determine final priority
        if professional_score > 0:
            priority = "HIGH PRIORITY"
        elif urgency_score > 15 or buying_intent > 30:
            priority = "HIGH PRIORITY" 
        elif urgency_score > 5 or buying_intent > 10 or business_score > 10:
            priority = "MEDIUM PRIORITY"
        else:
            priority = "LOW PRIORITY (N/A)"
        
        return {
            "urgency_score": min(100, urgency_score),
            "buying_intent": min(100, buying_intent),
            "business_score": min(100, business_score),
            "professional_score": min(100, professional_score),
            "total_priority": min(100, urgency_score + buying_intent + business_score + professional_score),
            "priority_level": priority,
            "detected_keywords": [word for word in professional_keywords + urgency_words + buying_words + business_words if word in text]
        }

class AutoEmailAnalyzer(BaseTool):
    name: str = "auto_email_analyzer"
    description: str = "Automatically analyze scanned emails for sentiment and priority"
    args_schema: Type[BaseModel] = EmailScanInput
    
    def _run(self, folder: str = "INBOX", limit: int = 5, unread_only: bool = True) -> str:
        """Scan and automatically analyze emails"""
        try:
            # First scan the inbox
            scanner = EmailInboxScanner()
            scan_result = scanner._run(folder, limit, unread_only)
            scan_data = json.loads(scan_result)
            
            if "error" in scan_data:
                return scan_result
            
            # Import sentiment analysis tool
            from .sentiment_tools import BasicSentimentTool
            sentiment_tool = BasicSentimentTool()
            
            analyzed_emails = []
            
            for email_data in scan_data.get("emails", []):
                # Analyze each email
                sentiment_result = sentiment_tool._run(
                    email_content=email_data["body"],
                    subject=email_data["subject"],
                    sender_email=email_data["sender"]
                )
                
                sentiment_data = json.loads(sentiment_result)
                
                # Combine email data with sentiment analysis
                analyzed_email = {
                    **email_data,
                    "sentiment_analysis": sentiment_data,
                    "recommended_action": self._get_recommended_action(sentiment_data),
                    "response_urgency": self._calculate_response_urgency(sentiment_data, email_data["priority_indicators"])
                }
                
                analyzed_emails.append(analyzed_email)
            
            # Sort by priority
            analyzed_emails.sort(key=lambda x: x["response_urgency"], reverse=True)
            
            result = {
                "status": "success",
                "total_analyzed": len(analyzed_emails),
                "high_priority": [e for e in analyzed_emails if e["response_urgency"] > 70],
                "medium_priority": [e for e in analyzed_emails if 40 <= e["response_urgency"] <= 70],
                "low_priority": [e for e in analyzed_emails if e["response_urgency"] < 40],
                "analyzed_emails": analyzed_emails,
                "summary": {
                    "requires_immediate_attention": len([e for e in analyzed_emails if e["response_urgency"] > 80]),
                    "potential_sales_opportunities": len([e for e in analyzed_emails if e["sentiment_analysis"].get("buying_intent", 0) > 60]),
                    "negative_sentiment_requiring_care": len([e for e in analyzed_emails if e["sentiment_analysis"].get("business_sentiment") == "negative"])
                }
            }
            
            return json.dumps(result, indent=2)
            
        except Exception as e:
            return json.dumps({"error": f"Auto analysis failed: {str(e)}"})
    
    def _get_recommended_action(self, sentiment_data: Dict[str, Any]) -> str:
        """Get recommended action based on sentiment analysis"""
        buying_intent = sentiment_data.get("buying_intent", 0)
        urgency = sentiment_data.get("urgency_level", 0)
        business_sentiment = sentiment_data.get("business_sentiment", "neutral")
        
        if buying_intent > 70 and urgency > 60:
            return "🚨 URGENT: High buying intent - Call immediately"
        elif buying_intent > 60:
            return "📞 HIGH PRIORITY: Schedule demo/meeting within 24 hours"
        elif business_sentiment == "negative":
            return "🤝 DAMAGE CONTROL: Personal response required to address concerns"
        elif urgency > 70:
            return "⏰ TIME SENSITIVE: Respond within 4 hours"
        elif buying_intent > 40:
            return "📧 FOLLOW UP: Send detailed information and schedule follow-up"
        else:
            return "📝 STANDARD: Respond within 24-48 hours"
    
    def _calculate_response_urgency(self, sentiment_data: Dict[str, Any], priority_indicators: Dict[str, Any]) -> int:
        """Calculate overall response urgency score"""
        buying_intent = sentiment_data.get("buying_intent", 0)
        urgency = sentiment_data.get("urgency_level", 0)
        business_sentiment = sentiment_data.get("business_sentiment", "neutral")
        
        # Base score from buying intent and urgency
        score = (buying_intent * 0.4) + (urgency * 0.3)
        
        # Boost for negative sentiment (needs attention)
        if business_sentiment == "negative":
            score += 20
        
        # Boost for high priority indicators from initial scan
        score += priority_indicators.get("total_priority", 0) * 0.3
        
        return min(100, int(score))
