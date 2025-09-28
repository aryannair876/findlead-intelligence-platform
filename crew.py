from crewai import Agent, Task, Crew, Process, LLM
from crewai.project import CrewBase, agent, crew, task
from tools import (
    BasicSentimentTool, UrgencyDetectionTool,
    BasicEmailValidatorTool, AdvancedEmailValidatorTool, DomainReputationTool,
    WebsiteContentFetcher, ChangeDetectionTool, WebsiteComprehensiveAnalyzer
)
import yaml
import json
import os
import time
from dotenv import load_dotenv
from utils.rate_limiter import groq_rate_limiter

# Load environment variables
load_dotenv()

@CrewBase
class OptimizedIntelligenceCrew():
    """FindLead Intelligence Platform - Comprehensive Multi-Agent System"""

    def __init__(self):
        # Get the directory where this file is located
        current_dir = os.path.dirname(os.path.abspath(__file__))
        
        # Load agent and task configurations using absolute paths
        agents_path = os.path.join(current_dir, 'config', 'agents.yaml')
        tasks_path = os.path.join(current_dir, 'config', 'tasks.yaml')
        
        print(f"🔍 Loading agents from: {agents_path}")
        print(f"🔍 Loading tasks from: {tasks_path}")
        
        with open(agents_path, 'r') as f:
            self.agents_data = yaml.safe_load(f)
        
        with open(tasks_path, 'r') as f:
            self.tasks_data = yaml.safe_load(f)

        # GroqCloud LLM Configuration - ULTRA Rate-Limited for Real AI
        self.groq_llm = LLM(
            model="llama-3.1-8b-instant",  # Fastest model
            api_key=os.getenv('GROQ_API_KEY'),
            api_base="https://api.groq.com/openai/v1",
            custom_llm_provider="groq",
            temperature=0.1,  # Very focused responses
            max_tokens=100,   # VERY low token limit
            request_timeout=30
        )
        
        # Backup OpenRouter LLM Configuration - Fallback option
        self.openrouter_llm = LLM(
            model="google/gemini-2.0-flash-exp:free",
            api_key=os.getenv('OPENROUTER_API_KEY'),
            api_base="https://openrouter.ai/api/v1",
            custom_llm_provider="openrouter"
        )

    # === EMAIL VALIDATION AGENTS ===
    @agent
    def domain_health_validator(self) -> Agent:
        agent_config = self.agents_data['domain_health_validator']
        return Agent(
            role=agent_config['role'],
            goal=agent_config['goal'],
            backstory=agent_config['backstory'],
            llm=self.groq_llm,
            verbose=True,
            tools=[BasicEmailValidatorTool(), AdvancedEmailValidatorTool(), DomainReputationTool()],
        )

    @agent  
    def reputation_intelligence_agent(self) -> Agent:
        agent_config = self.agents_data['reputation_intelligence_agent']
        return Agent(
            role=agent_config['role'],
            goal=agent_config['goal'],
            backstory=agent_config['backstory'],
            llm=self.groq_llm,
            verbose=True,
            tools=[DomainReputationTool(), AdvancedEmailValidatorTool()],
        )

    @agent
    def deliverability_risk_assessor(self) -> Agent:
        agent_config = self.agents_data['deliverability_risk_assessor']
        return Agent(
            role=agent_config['role'],
            goal=agent_config['goal'],
            backstory=agent_config['backstory'],
            llm=self.groq_llm,
            verbose=True,
        )

    # === SENTIMENT ANALYSIS AGENTS ===
    @agent
    def emotional_intelligence_analyzer(self) -> Agent:
        agent_config = self.agents_data['emotional_intelligence_analyzer']
        return Agent(
            role=agent_config['role'],
            goal=agent_config['goal'],
            backstory=agent_config['backstory'],
            llm=self.groq_llm,
            verbose=True,
            tools=[BasicSentimentTool(), UrgencyDetectionTool()],
        )

    @agent
    def buyer_intent_detector(self) -> Agent:
        agent_config = self.agents_data['buyer_intent_detector']
        return Agent(
            role=agent_config['role'],
            goal=agent_config['goal'],
            backstory=agent_config['backstory'],
            llm=self.groq_llm,
            verbose=True,
            tools=[BasicSentimentTool(), UrgencyDetectionTool()],
        )

    @agent
    def response_strategy_optimizer(self) -> Agent:
        agent_config = self.agents_data['response_strategy_optimizer']
        return Agent(
            role=agent_config['role'],
            goal=agent_config['goal'],
            backstory=agent_config['backstory'],
            llm=self.groq_llm,
            verbose=True,
        )

    # === WEBSITE MONITORING AGENTS ===
    @agent
    def web_monitoring_specialist(self) -> Agent:
        agent_config = self.agents_data['web_monitoring_specialist']
        return Agent(
            role=agent_config['role'],
            goal=agent_config['goal'],
            backstory=agent_config['backstory'],
            llm=self.groq_llm,
            verbose=True,
            tools=[WebsiteContentFetcher(), ChangeDetectionTool(), WebsiteComprehensiveAnalyzer()],
        )

    @agent
    def competitive_intelligence_analyst(self) -> Agent:
        agent_config = self.agents_data['competitive_intelligence_analyst']
        return Agent(
            role=agent_config['role'],
            goal=agent_config['goal'],
            backstory=agent_config['backstory'],
            llm=self.groq_llm,
            verbose=True,
            tools=[WebsiteContentFetcher(), WebsiteComprehensiveAnalyzer()],
        )

    @agent
    def strategic_response_coordinator(self) -> Agent:
        agent_config = self.agents_data['strategic_response_coordinator']
        return Agent(
            role=agent_config['role'],
            goal=agent_config['goal'],
            backstory=agent_config['backstory'],
            llm=self.groq_llm,
            verbose=True,
        )

    # === EMAIL VALIDATION TASKS ===
    @task
    def domain_infrastructure_validation(self) -> Task:
        task_config = self.tasks_data['domain_infrastructure_validation']
        return Task(
            description=task_config['description'],
            expected_output=task_config['expected_output'],
            agent=self.domain_health_validator(),
            output_file='data/snapshots/domain_validation_report.json'
        )
    
    @task
    def reputation_intelligence_analysis(self) -> Task:
        task_config = self.tasks_data['reputation_intelligence_analysis']
        return Task(
            description=task_config['description'],
            expected_output=task_config['expected_output'],
            agent=self.reputation_intelligence_agent(),
            context=[self.domain_infrastructure_validation()],  # Add context dependency
            output_file='data/snapshots/reputation_analysis_report.json'
        )

    @task
    def strategic_risk_assessment(self) -> Task:
        task_config = self.tasks_data['strategic_risk_assessment']
        return Task(
            description=task_config['description'],
            expected_output=task_config['expected_output'],
            agent=self.deliverability_risk_assessor(),
            context=[self.domain_infrastructure_validation(), self.reputation_intelligence_analysis()],  # Add context dependencies
            output_file='data/snapshots/strategic_risk_assessment.json'
        )
        
    # === SENTIMENT ANALYSIS TASKS ===
    @task
    def emotional_context_analysis(self) -> Task:
        task_config = self.tasks_data['emotional_context_analysis']
        return Task(
            description=task_config['description'],
            expected_output=task_config['expected_output'],
            agent=self.emotional_intelligence_analyzer(),
            output_file='data/snapshots/emotional_analysis_report.json'
        )
    
    @task
    def buyer_intent_detection(self) -> Task:
        task_config = self.tasks_data['buyer_intent_detection']
        return Task(
            description=task_config['description'],
            expected_output=task_config['expected_output'],
            agent=self.buyer_intent_detector(),
            context=[self.emotional_context_analysis()],  # Add context dependency
            output_file='data/snapshots/buyer_intent_report.json'
        )
    
    @task
    def response_strategy_optimization(self) -> Task:
        task_config = self.tasks_data['response_strategy_optimization']
        return Task(
            description=task_config['description'],
            expected_output=task_config['expected_output'],
            agent=self.response_strategy_optimizer(),
            context=[self.emotional_context_analysis(), self.buyer_intent_detection()],  # Add context dependencies
            output_file='data/snapshots/response_strategy_report.json'
        )

    # === WEBSITE MONITORING TASKS ===
    @task
    def comprehensive_change_detection(self) -> Task:
        task_config = self.tasks_data['comprehensive_change_detection']
        return Task(
            description=task_config['description'],
            expected_output=task_config['expected_output'],
            agent=self.web_monitoring_specialist(),
            output_file='data/snapshots/change_detection_report.json'
        )

    @task
    def strategic_intelligence_analysis(self) -> Task:
        task_config = self.tasks_data['strategic_intelligence_analysis']
        return Task(
            description=task_config['description'],
            expected_output=task_config['expected_output'],
            agent=self.competitive_intelligence_analyst(),
            context=[self.comprehensive_change_detection()],  # Add context dependency
            output_file='data/snapshots/strategic_intelligence_briefing.json'
        )

    @task
    def action_strategy_development(self) -> Task:
        task_config = self.tasks_data['action_strategy_development']
        return Task(
            description=task_config['description'],
            expected_output=task_config['expected_output'],
            agent=self.strategic_response_coordinator(),
            context=[self.comprehensive_change_detection(), self.strategic_intelligence_analysis()],  # Add context dependencies
            output_file='data/snapshots/action_strategy_plan.json'
        )

    # === CREW DEFINITIONS ===
    @crew
    def email_validation_crew(self) -> Crew:
        """Comprehensive email validation and risk assessment crew"""
        return Crew(
            agents=[
                self.domain_health_validator(),
                self.reputation_intelligence_agent(),
                self.deliverability_risk_assessor()
            ],
            tasks=[
                self.domain_infrastructure_validation(),
                self.reputation_intelligence_analysis(), 
                self.strategic_risk_assessment()
            ],
            verbose=True,
            process=Process.sequential
        )

    @crew  
    def sentiment_analysis_crew(self) -> Crew:
        """Advanced sentiment and buyer intent analysis crew"""
        return Crew(
            agents=[
                self.emotional_intelligence_analyzer(),
                self.buyer_intent_detector(),
                self.response_strategy_optimizer()
            ],
            tasks=[
                self.emotional_context_analysis(),
                self.buyer_intent_detection(),
                self.response_strategy_optimization()
            ],
            verbose=True,
            process=Process.sequential
        )

    @crew
    def website_monitoring_crew(self) -> Crew:
        """Competitive intelligence and website monitoring crew"""
        return Crew(
            agents=[
                self.web_monitoring_specialist(),
                self.competitive_intelligence_analyst(),
                self.strategic_response_coordinator()
            ],
            tasks=[
                self.comprehensive_change_detection(),
                self.strategic_intelligence_analysis(),
                self.action_strategy_development()
            ],
            verbose=True,
            process=Process.sequential
        )

    # === MAIN EXECUTION METHODS WITH RATE LIMITING ===
    def analyze_email_sentiment(self, email_content: str, subject: str = "", sender_email: str = ""):
        """Run optimized sentiment analysis on email content with rate limiting"""
        print(f"🔍 Analyzing sentiment for email: {subject}")
        
        # Check rate limit before proceeding
        try:
            groq_rate_limiter.wait_if_needed()
        except Exception as rate_error:
            print(f"⚠️ Rate limit exceeded: {rate_error}")
            return {
                'status': 'rate_limited',
                'error': str(rate_error),
                'sentiment': 'neutral',  # fallback
                'urgency': 'low',
                'key_points': ['Rate limit exceeded - analysis deferred']
            }
        
        # Strategy: Use single comprehensive call to preserve quota
        print("⚡ Using quota-efficient single-call analysis")
        
        try:
            # Add small delay to prevent rapid-fire requests
            time.sleep(0.5)
            
            # Get one agent to do comprehensive analysis in one call
            analyzer = self.emotional_intelligence_analyzer()
            
            # Ultra-concise prompt for rate limit compliance
            analysis_prompt = f"""
            Business analysis for: {subject[:50]} | {email_content[:200]}

            JSON only:
            {{
                "sentiment": "positive/neutral/negative", 
                "buying_intent": "high/medium/low",
                "urgency_level": 0-100
            }}

            Rules: Budget+demo+urgent=positive/high. Frustrated buyer=positive.
            """
            
            # Use the agent's LLM directly for efficiency
            result = analyzer.llm.complete(analysis_prompt)
            print(f"✅ Single-call analysis completed: {str(result)[:200]}...")
            return result
            
        except Exception as e:
            print(f"❌ Optimized analysis failed: {e}")
            print("🔄 Falling back to basic multi-agent crew (may hit quota limits)")
            
            # Only fall back to full crew if really necessary
            crew = self.sentiment_analysis_crew()
            inputs = {
                'email_content': email_content,
                'subject': subject,
                'sender_email': sender_email,
                'prospect_name': sender_email.split('@')[0] if '@' in sender_email else 'Unknown'
            }
            return crew.kickoff(inputs=inputs)

    def validate_email_domain(self, email_address: str):
        """Run comprehensive email validation"""
        print(f"🔍 Validating email domain: {email_address}")
        domain = email_address.split('@')[1] if '@' in email_address else email_address
        crew = self.email_validation_crew()
        
        inputs = {
            'email_address': email_address,
            'email_domain': domain
        }
        
        return crew.kickoff(inputs=inputs)

    def monitor_website(self, website_url: str):
        """Run website monitoring and competitive analysis with rate limiting"""
        print(f"🌐 Monitoring website: {website_url}")
        
        # Check rate limit before proceeding
        try:
            groq_rate_limiter.wait_if_needed()
        except Exception as rate_error:
            print(f"⚠️ Rate limit exceeded: {rate_error}")
            return {
                'status': 'rate_limited',
                'error': str(rate_error),
                'website_url': website_url,
                'analysis': 'Rate limit exceeded - analysis deferred'
            }
        
        # Add delay to prevent rapid requests
        time.sleep(1.0)  # Longer delay for website analysis as it uses more tokens
        
        crew = self.website_monitoring_crew()
        
        inputs = {
            'website_url': website_url,
            'target_url': website_url,
            'target_website': website_url  # Add missing variable
        }
        
        try:
            result = crew.kickoff(inputs=inputs)
            
            # Check if result is empty or None
            if not result or result is None:
                print("⚠️ CrewAI returned empty result - providing fallback")
                return {
                    'status': 'partial',
                    'error': 'LLM returned empty response',
                    'website_url': website_url,
                    'analysis': f'Website {website_url} was analyzed but LLM provided empty response. This may be due to rate limiting or model issues.',
                    'fallback_data': {
                        'title': 'Analysis Incomplete',
                        'status_code': 'unknown',
                        'basic_info': f'Attempted analysis of {website_url}'
                    }
                }
            
            # Check if result is a string that indicates failure
            if isinstance(result, str) and ('error' in result.lower() or 'failed' in result.lower()):
                print(f"⚠️ CrewAI returned error string: {result}")
                return {
                    'status': 'error',
                    'error': 'Analysis failed with error message',
                    'website_url': website_url,
                    'analysis': result
                }
            
            return result
            
        except Exception as e:
            if 'rate' in str(e).lower() or 'limit' in str(e).lower():
                print(f"🚫 Rate limit hit during website analysis: {e}")
                return {
                    'status': 'rate_limited',
                    'error': 'Rate limit exceeded during analysis',
                    'website_url': website_url,
                    'analysis': 'Analysis failed due to rate limiting'
                }
            
            # Handle other exceptions
            print(f"❌ Unexpected error during crew execution: {e}")
            return {
                'status': 'error',
                'error': f'Crew execution failed: {str(e)}',
                'website_url': website_url,
                'analysis': f'Analysis of {website_url} failed due to system error: {str(e)}'
            }

    def run_priority_assessment(self, email_data: dict):
        """Run priority assessment for email analysis"""
        print(f"📊 Running priority assessment for email")
        
        # Use sentiment crew for comprehensive email analysis
        crew = self.sentiment_analysis_crew()
        
        inputs = {
            'email_content': email_data.get('body', ''),
            'subject': email_data.get('subject', ''),
            'sender_email': email_data.get('sender', ''),
            'recipient': email_data.get('recipient', '')
        }
        
        return crew.kickoff(inputs=inputs)
