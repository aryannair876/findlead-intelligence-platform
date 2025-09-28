from groq import Groq
import re
from typing import Type, Dict, Any
from pydantic import BaseModel, Field
from crewai.tools import BaseTool
import os
from datetime import datetime
import json

class EmailSentimentInput(BaseModel):
    email_content: str = Field(..., description="Email content to analyze")
    sender_email: str = Field(default="", description="Sender's email address")
    subject: str = Field(default="", description="Email subject line")

class BasicSentimentTool(BaseTool):
    name: str = "basic_sentiment_analyzer"
    description: str = "Analyzes email sentiment and emotional tone using Groq API with OpenAI GPT-OSS-20B model"
    args_schema: Type[BaseModel] = EmailSentimentInput
    
    def _run(self, email_content: str, sender_email: str = "", subject: str = "") -> str:
        try:
            # First do a quick local analysis as backup
            local_analysis = self._local_sentiment_analysis(email_content, subject)
            
            # Configure Groq API
            api_key = os.getenv('GROQ_API_KEY')
            if not api_key:
                return json.dumps(local_analysis)
            
            prompt = f"""
            Analyze this email for BUSINESS SENTIMENT and buying intent, not emotional tone:
            
            Subject: {subject}
            From: {sender_email}
            Content: {email_content}
            
            CRITICAL RULES FOR BUSINESS SENTIMENT:
            - POSITIVE: Customer wants to buy, asking for demo/pricing, has budget, ready to purchase, seeking solution to problem
            - NEGATIVE: Not interested, found alternative, canceling, no budget, rejecting offers
            - NEUTRAL: Just asking questions, gathering info, no clear buying signal
            
            IMPORTANT: Frustrated customer with budget who wants demo = POSITIVE (high buying intent)
            
            Example Analysis:
            "Frustrated with current system, budget approved, need demo ASAP" = POSITIVE sentiment (90+ buying intent)
            "Just curious about your product features" = NEUTRAL sentiment (30-50 buying intent)
            "Not interested, found another solution" = NEGATIVE sentiment (0-20 buying intent)
            
            Analyze this email and respond with ONLY a JSON object:
            {{
                "business_sentiment": "positive|negative|neutral",
                "sentiment_score": -1.0 to 1.0,
                "emotions": ["urgency", "frustration", "excitement", etc],
                "urgency_level": 0-100,
                "buying_intent": 0-100,
                "key_phrases": ["budget approved", "need demo", etc],
                "response_priority": "low|medium|high",
                "business_context": "explanation of why this sentiment was chosen"
            }}
            """
            
            # Use Groq client with the new Llama Guard 4 model
            client = Groq(api_key=api_key)
            completion = client.chat.completions.create(
                model="meta-llama/llama-guard-4-12b",
                messages=[
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=0.3,  # Lower temperature for more consistent business analysis
                max_tokens=1024,
                top_p=1,
                stream=False,
                stop=None
            )
            
            content = completion.choices[0].message.content.strip()
            
            # Try to parse as JSON
            try:
                # Extract JSON from the response if it's wrapped in markdown
                if "```json" in content:
                    content = content.split("```json")[1].split("```")[0].strip()
                elif "```" in content:
                    content = content.split("```")[1].strip()
                
                parsed_result = json.loads(content)
                # Merge with local analysis if API result is incomplete
                if parsed_result.get('sentiment_score', 0) == 0 and local_analysis['sentiment_score'] > 0:
                    parsed_result.update(local_analysis)
                
                return json.dumps(parsed_result, indent=2)
            except json.JSONDecodeError:
                # Return local analysis as fallback
                local_analysis['raw_api_response'] = content
                return json.dumps(local_analysis, indent=2)

        except Exception as e:
            # Return local analysis with error info
            local_analysis = self._local_sentiment_analysis(email_content, subject)
            local_analysis['api_error'] = str(e)
            return json.dumps(local_analysis, indent=2)
    
    def _local_sentiment_analysis(self, email_content: str, subject: str = "") -> Dict[str, Any]:
        """Perform local business sentiment analysis as backup"""
        # Normalize text: combine subject + content and clean it
        raw_text = f"{subject} {email_content}"
        text = raw_text.lower()
        # Replace underscores and other separators with spaces for better matching
        text = text.replace('_', ' ').replace('-', ' ').replace('.', ' ')
        
        # Professional/Important indicators (high priority regardless of buying intent)
        professional_high_priority = [
            'github', 'linkedin', 'job', 'hiring', 'interview', 'career',
            'invitation', 'collaborate', 'pull request', 'repository', 'organization',
            'team', 'project', 'developer', 'engineer', 'opportunity', 'position',
            'goldman sachs', 'microsoft', 'google', 'amazon', 'apple', 'facebook',
            'software engineer', 'hackathon', 'hackathons', 'devpost', 'coding',
            'programming', 'technical', 'startup', 'internship', 'full-time',
            'part-time', 'remote', 'work from home', 'salary', 'benefits',
            'recruiter', 'hr', 'human resources', 'talent', 'application'
        ]
        
        # Business positive indicators (show buying intent)
        business_positive = [
            'demo', 'pricing', 'price', 'purchase', 'buy', 'contract', 'solution', 
            'interested', 'ready', 'decision', 'budget approved', 'budget is approved', 'budget', 'timeline', 'when can we',
            'looking forward', 'excited to', 'want to proceed', 'move forward',
            'schedule', 'meeting', 'call', 'discuss', 'evaluate', 'need to find',
            'replacement', 'alternative', 'help us', 'can you help', 'asap',
            'this week', 'looking for', 'current system', 'losing productivity',
            'crashing', 'frustrated with current', 'need a replacement'
        ]
        
        # Business negative indicators (not interested in buying)  
        business_negative = [
            'not interested', 'cancel', 'unsubscribe', 'too expensive', 'no budget',
            'looking elsewhere', 'found alternative', 'decided against', 'not a fit',
            'not right now', 'maybe later', 'wrong time'
        ]
        
        # Emotional words (separate from business intent)
        emotional_positive = ['great', 'excellent', 'perfect', 'love', 'amazing', 'fantastic']
        emotional_negative = ['frustrated', 'annoying', 'terrible', 'hate', 'awful', 'disappointed']
        
        # Urgency indicators
        urgency_words = [
            'urgent', 'asap', 'as soon as possible', 'immediately', 'quickly', 'soon', 
            'this week', 'friday', 'deadline', 'crashing', 'constantly crashing',
            'losing productivity', 'need to find', 'replacement asap'
        ]
        
        # Calculate scores
        professional_score = sum(1 for word in professional_high_priority if word in text)
        business_pos_score = sum(1 for word in business_positive if word in text)
        business_neg_score = sum(1 for word in business_negative if word in text)
        
        # Calculate emotional tone (secondary)
        emotional_pos_score = sum(1 for word in emotional_positive if word in text)
        emotional_neg_score = sum(1 for word in emotional_negative if word in text)
        
        # Calculate other scores
        urgency_score = sum(1 for word in urgency_words if word in text)
        
        # Priority override for professional communications
        if professional_score > 0:
            # GitHub, LinkedIn, job-related emails should be high priority
            business_sentiment = "neutral"  # Professional, not sales-related
            sentiment_score = 0.2
            buying_intent = 20  # Low buying intent but high importance
        elif business_pos_score > business_neg_score:
            # Strong business interest = positive sentiment regardless of emotional tone
            business_sentiment = "positive"
            sentiment_score = min(0.9, 0.5 + (business_pos_score * 0.2))
            buying_intent = min(100, business_pos_score * 20 + 50)
            
            # Special case: If budget is mentioned + demo requested + urgency = very high intent
            if 'budget' in text and ('demo' in text or 'help us' in text) and urgency_score > 0:
                buying_intent = 90
                sentiment_score = 0.9
        elif business_neg_score > business_pos_score:
            # Clear business rejection = negative sentiment
            business_sentiment = "negative" 
            sentiment_score = max(-0.8, -0.4 - (business_neg_score * 0.2))
            buying_intent = max(0, 20 - (business_neg_score * 10))
        else:
            # No clear business signals, check for general inquiry
            if any(word in text for word in ['question', 'info', 'information', 'tell me', 'how does']):
                business_sentiment = "neutral"
                sentiment_score = 0.1
                buying_intent = 40
            else:
                business_sentiment = "neutral"
                sentiment_score = 0.0
                buying_intent = 30
        
        # Detect emotions (separate from business sentiment)
        emotions = []
        if urgency_score > 0:
            emotions.append('urgency')
        if business_pos_score > 0:
            emotions.append('curiosity')
        if professional_score > 0:
            emotions.append('professional')
        if emotional_pos_score > emotional_neg_score:
            emotions.append('excitement')
        elif emotional_neg_score > emotional_pos_score:
            emotions.append('frustration')
        if any(word in text for word in ['concern', 'worried', 'doubt']):
            emotions.append('skepticism')
        
        if not emotions:
            emotions = ['neutral']
        
        # Calculate urgency level
        urgency_level = min(100, urgency_score * 30 + (50 if any(word in text for word in ['asap', 'urgent']) else 0))
        
        # Determine priority based on business factors and professional importance
        if professional_score > 0:
            # Professional emails (GitHub, LinkedIn, jobs, hiring) are high priority
            priority = 'high'
        elif buying_intent > 70 or urgency_level > 70:
            priority = 'high'
        elif buying_intent > 40 or urgency_level > 40:
            priority = 'medium'
        else:
            priority = 'low'
        
        # Business context explanation
        context_reasons = []
        if professional_score > 0:
            context_reasons.append(f"contains professional/career-related content ({professional_score} professional indicators)")
        if business_pos_score > 0:
            context_reasons.append(f"shows buying interest ({business_pos_score} business positive indicators)")
        if business_neg_score > 0:
            context_reasons.append(f"indicates lack of interest ({business_neg_score} business negative indicators)")
        if urgency_score > 0:
            context_reasons.append(f"expresses urgency ({urgency_score} urgency indicators)")
        
        business_context = f"Classified as {business_sentiment} because email " + (
            "; ".join(context_reasons) if context_reasons 
            else "shows neutral business intent with no clear buying signals"
        )
        
        return {
            "business_sentiment": business_sentiment,
            "sentiment_score": sentiment_score,
            "emotions": emotions,
            "urgency_level": urgency_level,
            "buying_intent": buying_intent,
            "key_phrases": [word for word in professional_high_priority + business_positive + urgency_words if word in text],
            "priority": priority,  # Changed from response_priority
            "response_priority": priority,  # Keep both for compatibility
            "business_context": business_context,
            "analysis_method": "local_business_focused",
            "professional_score": professional_score,
            "debug_keywords_found": [word for word in professional_high_priority if word in text]
        }

class UrgencyDetectionTool(BaseTool):
    name: str = "urgency_detector"
    description: str = "Detects urgency indicators in email content"
    args_schema: Type[BaseModel] = EmailSentimentInput
    
    def _run(self, email_content: str, sender_email: str = "", subject: str = "") -> str:
        # Urgency keywords and patterns
        urgency_patterns = {
            "high": [
                "asap", "urgent", "immediately", "right away", "deadline",
                "time sensitive", "expires today", "limited time",
                "need by", "rush", "emergency", "critical", "constantly crashing",
                "losing productivity", "need a replacement", "this week"
            ],
            "medium": [
                "soon", "quickly", "fast", "priority", "important",
                "this week", "end of month", "quarter", "by friday"
            ],
            "low": [
                "when you can", "no rush", "whenever", "eventually",
                "at your convenience", "flexible"
            ]
        }
        
        text = f"{subject} {email_content}".lower()
        urgency_score = 0
        detected_phrases = []
        
        # Check for high urgency (60-100 points)
        for phrase in urgency_patterns["high"]:
            if phrase in text:
                urgency_score = max(urgency_score, 80)
                detected_phrases.append(phrase)
        
        # Check for medium urgency (30-60 points)
        for phrase in urgency_patterns["medium"]:
            if phrase in text:
                urgency_score = max(urgency_score, 50)
                detected_phrases.append(phrase)
        
        # Check for low urgency (0-30 points)
        for phrase in urgency_patterns["low"]:
            if phrase in text:
                urgency_score = min(urgency_score, 20)
                detected_phrases.append(phrase)
        
        # Default medium if no patterns found
        if urgency_score == 0:
            urgency_score = 35
        
        result = {
            "urgency_score": urgency_score,
            "detected_phrases": detected_phrases,
            "urgency_level": "high" if urgency_score > 60 else "medium" if urgency_score > 30 else "low"
        }
        
        return json.dumps(result, indent=2)
