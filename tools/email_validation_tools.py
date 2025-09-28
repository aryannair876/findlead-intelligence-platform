import dns.resolver
import re
import socket
from email_validator import validate_email, EmailNotValidError
from crewai.tools import BaseTool
from typing import Type
from pydantic import BaseModel, Field
import requests
import json

class EmailValidationInput(BaseModel):
    email: str = Field(..., description="Email address to validate")

class BasicEmailValidatorTool(BaseTool):
    name: str = "basic_email_validator"
    description: str = "Validates email syntax and checks MX records"
    args_schema: Type[BaseModel] = EmailValidationInput
    
    def _run(self, email: str) -> str:
        results = {
            "email": email,
            "syntax_valid": False,
            "mx_valid": False,
            "domain": "",
            "risk_score": 0,
            "valid": False
        }
        
        try:
            # First check basic email format with regex
            email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
            if re.match(email_pattern, email):
                results["syntax_valid"] = True
                results["valid"] = True
                
                # Extract domain
                domain = email.split('@')[1]
                results["domain"] = domain
                
                # MX record check for common domains
                known_valid_domains = ['gmail.com', 'yahoo.com', 'outlook.com', 'hotmail.com', 'icloud.com']
                if domain.lower() in known_valid_domains:
                    results["mx_valid"] = True
                    results["risk_score"] = 10  # Very low risk for known providers
                else:
                    # Try actual MX lookup for other domains
                    try:
                        mx_records = dns.resolver.resolve(domain, 'MX')
                        if mx_records:
                            results["mx_valid"] = True
                            results["risk_score"] = 20  # Low risk
                        else:
                            results["risk_score"] = 80  # High risk
                    except dns.resolver.NXDOMAIN:
                        results["mx_valid"] = False
                        results["risk_score"] = 90  # Very high risk - domain doesn't exist
                    except Exception as dns_e:
                        # For DNS errors, assume it's valid but with medium risk
                        results["mx_valid"] = True
                        results["risk_score"] = 40  # Medium risk due to DNS uncertainty
                        results["dns_note"] = "DNS lookup failed, assumed valid"
            else:
                results["syntax_valid"] = False
                results["valid"] = False
                results["risk_score"] = 100  # Invalid format
                
        except Exception as e:
            results["syntax_valid"] = False
            results["valid"] = False
            results["risk_score"] = 95
            results["error"] = str(e)
            results["error"] = str(e)
            results["risk_score"] = 100  # Maximum risk
        except Exception as e:
            results["error"] = str(e)
            results["risk_score"] = 90  # High risk due to unknown error
            
        return json.dumps(results, indent=2)

class AdvancedEmailValidatorTool(BaseTool):
    name: str = "advanced_email_validator"
    description: str = "Advanced email validation with reputation checking"
    args_schema: Type[BaseModel] = EmailValidationInput
    
    def _run(self, email: str) -> str:
        domain = email.split('@')[1] if '@' in email else ''
        
        results = {
            "email": email,
            "domain": domain,
            "syntax_valid": False,
            "mx_valid": False,
            "reputation_score": 0,
            "is_disposable": False,
            "is_free_provider": False,
            "risk_level": "unknown",
            "risk_factors": []
        }
        
        try:
            # Basic syntax validation
            valid = validate_email(email)
            results["syntax_valid"] = True
            results["domain"] = valid.domain
            domain = valid.domain
            
            # MX Record Check
            try:
                mx_records = dns.resolver.resolve(domain, 'MX')
                results["mx_valid"] = bool(mx_records)
                results["mx_count"] = len(mx_records)
            except dns.resolver.NXDOMAIN:
                results["mx_valid"] = False
                results["risk_factors"].append("Domain does not exist")
            except Exception as e:
                results["mx_valid"] = False
                results["risk_factors"].append(f"DNS lookup failed: {str(e)}")
            
            # Check for disposable email providers
            disposable_domains = [
                '10minutemail.com', 'tempmail.org', 'guerrillamail.com',
                'mailinator.com', 'yopmail.com', 'temp-mail.org',
                'throwaway.email', 'maildrop.cc', 'mohmal.com',
                'sharklasers.com', 'guerrillamailblock.com'
            ]
            results["is_disposable"] = domain.lower() in disposable_domains
            
            # Check for free email providers
            free_providers = [
                'gmail.com', 'yahoo.com', 'hotmail.com', 'outlook.com',
                'aol.com', 'icloud.com', 'protonmail.com', 'mail.com'
            ]
            results["is_free_provider"] = domain.lower() in free_providers
            
            # Calculate risk score
            risk_score = 0
            
            if not results["syntax_valid"]:
                risk_score += 50
                results["risk_factors"].append("Invalid email syntax")
            
            if not results["mx_valid"]:
                risk_score += 40
                results["risk_factors"].append("No valid MX records found")
            
            if results["is_disposable"]:
                risk_score += 60
                results["risk_factors"].append("Disposable/temporary email provider")
            
            # Free providers have slightly higher risk for business use
            if results["is_free_provider"]:
                risk_score += 10
                results["risk_factors"].append("Free email provider")
            
            # Check domain age (simplified - in real implementation you'd use WHOIS)
            if domain.lower() in ['test.com', 'example.com', 'invalid.com']:
                risk_score += 30
                results["risk_factors"].append("Test or example domain")
            
            results["risk_score"] = min(risk_score, 100)
            
            # Determine risk level
            if risk_score < 20:
                results["risk_level"] = "low"
            elif risk_score < 50:
                results["risk_level"] = "medium"
            elif risk_score < 80:
                results["risk_level"] = "high"
            else:
                results["risk_level"] = "very_high"
                
        except EmailNotValidError as e:
            results["error"] = str(e)
            results["risk_score"] = 100
            results["risk_level"] = "very_high"
            results["risk_factors"].append(f"Email validation error: {str(e)}")
        except Exception as e:
            results["error"] = str(e)
            results["risk_score"] = 85
            results["risk_level"] = "high"
            results["risk_factors"].append(f"Unexpected error: {str(e)}")
            
        return json.dumps(results, indent=2)

class DomainReputationTool(BaseTool):
    name: str = "domain_reputation_checker"
    description: str = "Check domain reputation and blacklist status"
    args_schema: Type[BaseModel] = EmailValidationInput
    
    def _run(self, email: str) -> str:
        domain = email.split('@')[1] if '@' in email else ''
        
        results = {
            "domain": domain,
            "reputation_checks": {},
            "blacklist_status": "unknown",
            "reputation_score": 50  # Default neutral score
        }
        
        try:
            # Simplified reputation check (in real implementation, you'd use reputation APIs)
            
            # Check against known bad domains
            known_bad_domains = [
                'spam.com', 'fake.com', 'scam.com', 'malware.com'
            ]
            
            # Check against known good domains
            known_good_domains = [
                'gmail.com', 'outlook.com', 'yahoo.com', 'apple.com',
                'microsoft.com', 'google.com', 'amazon.com'
            ]
            
            if domain.lower() in known_bad_domains:
                results["blacklist_status"] = "blacklisted"
                results["reputation_score"] = 10
                results["reputation_checks"]["manual_check"] = "Found in known bad domains"
            elif domain.lower() in known_good_domains:
                results["blacklist_status"] = "clean"
                results["reputation_score"] = 90
                results["reputation_checks"]["manual_check"] = "Found in known good domains"
            else:
                results["blacklist_status"] = "unknown"
                results["reputation_score"] = 50
                results["reputation_checks"]["manual_check"] = "Domain not in known lists"
            
            # Additional checks could include:
            # - DNS-based blackhole lists (DNSBL)
            # - Reputation services APIs
            # - Historical spam data
            
        except Exception as e:
            results["error"] = str(e)
            results["reputation_score"] = 30  # Lower score due to error
            
        return json.dumps(results, indent=2)
