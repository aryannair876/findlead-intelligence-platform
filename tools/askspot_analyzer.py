import requests
import ssl
import socket
from urllib.parse import urlparse, urljoin
from bs4 import BeautifulSoup
from crewai.tools import BaseTool
from pydantic import BaseModel, Field
from typing import Type, Dict, List
import json
import time
import re
import dns.resolver
from datetime import datetime, timedelta
import subprocess
import platform

class ComprehensiveAnalysisInput(BaseModel):
    url: str = Field(..., description="Website URL to analyze comprehensively")

class WebsiteComprehensiveAnalyzer(BaseTool):
    name: str = "website_comprehensive_analyzer"
    description: str = "Performs comprehensive website analysis including security, performance, SEO, and accessibility"
    args_schema: Type[BaseModel] = ComprehensiveAnalysisInput
    
    def _run(self, url: str) -> str:
        try:
            # Ensure URL has protocol
            if not url.startswith(('http://', 'https://')):
                url = 'https://' + url
                
            parsed_url = urlparse(url)
            domain = parsed_url.netloc
            
            # Initialize result structure
            analysis_result = {
                "url": url,
                "domain": domain,
                "analysis_timestamp": datetime.now().isoformat(),
                "security_analysis": {},
                "performance_analysis": {},
                "seo_analysis": {},
                "accessibility_analysis": {},
                "technical_analysis": {},
                "overall_score": 0,
                "recommendations": [],
                "critical_issues": []
            }
            
            # Perform all analysis components
            analysis_result["security_analysis"] = self._analyze_security(url, domain)
            analysis_result["performance_analysis"] = self._analyze_performance(url)
            analysis_result["seo_analysis"] = self._analyze_seo(url)
            analysis_result["accessibility_analysis"] = self._analyze_accessibility(url)
            analysis_result["technical_analysis"] = self._analyze_technical(url, domain)
            
            # Calculate overall score
            analysis_result["overall_score"] = self._calculate_overall_score(analysis_result)
            
            # Generate recommendations
            analysis_result["recommendations"] = self._generate_recommendations(analysis_result)
            
            return json.dumps(analysis_result, indent=2)
            
        except Exception as e:
            return json.dumps({
                "url": url,
                "error": f"Analysis failed: {str(e)}",
                "timestamp": datetime.now().isoformat()
            })
    
    def _analyze_security(self, url: str, domain: str) -> Dict:
        """Comprehensive security analysis"""
        security_score = 100
        issues = []
        
        try:
            # Check HTTPS
            https_enabled = url.startswith('https://')
            if not https_enabled:
                security_score -= 30
                issues.append("No HTTPS encryption detected")
            
            # SSL Certificate Analysis
            ssl_info = {}
            if https_enabled:
                try:
                    context = ssl.create_default_context()
                    with socket.create_connection((domain, 443), timeout=10) as sock:
                        with context.wrap_socket(sock, server_hostname=domain) as ssock:
                            cert = ssock.getpeercert()
                            ssl_info = {
                                "issuer": dict(x[0] for x in cert['issuer']),
                                "subject": dict(x[0] for x in cert['subject']),
                                "version": cert['version'],
                                "expiry_date": cert['notAfter'],
                                "valid": True
                            }
                            
                            # Check cert expiry
                            expiry = datetime.strptime(cert['notAfter'], '%b %d %H:%M:%S %Y %Z')
                            days_until_expiry = (expiry - datetime.now()).days
                            
                            if days_until_expiry < 30:
                                security_score -= 20
                                issues.append(f"SSL certificate expires in {days_until_expiry} days")
                            elif days_until_expiry < 90:
                                security_score -= 10
                                issues.append(f"SSL certificate expires in {days_until_expiry} days")
                                
                except Exception as e:
                    security_score -= 25
                    issues.append(f"SSL certificate error: {str(e)[:50]}")
            
            # Check security headers
            try:
                response = requests.get(url, timeout=10, allow_redirects=True)
                headers = response.headers
                
                security_headers = {
                    'X-Frame-Options': 'Clickjacking protection',
                    'X-XSS-Protection': 'XSS protection',
                    'X-Content-Type-Options': 'MIME type sniffing protection',
                    'Strict-Transport-Security': 'HTTPS enforcement',
                    'Content-Security-Policy': 'Content injection protection',
                    'Referrer-Policy': 'Referrer information control',
                    'Permissions-Policy': 'Feature policy control'
                }
                
                missing_headers = []
                for header, description in security_headers.items():
                    if header not in headers:
                        missing_headers.append(f"{header} ({description})")
                        security_score -= 5
                
                if missing_headers:
                    issues.append(f"Missing security headers: {', '.join(missing_headers[:3])}")
                
            except Exception as e:
                security_score -= 15
                issues.append("Could not analyze security headers")
            
            return {
                "score": max(0, security_score),
                "https_enabled": https_enabled,
                "ssl_info": ssl_info,
                "issues": issues,
                "grade": self._get_grade(max(0, security_score))
            }
            
        except Exception as e:
            return {
                "score": 0,
                "error": str(e),
                "grade": "F"
            }
    
    def _analyze_performance(self, url: str) -> Dict:
        """Performance analysis"""
        performance_score = 100
        issues = []
        metrics = {}
        
        try:
            start_time = time.time()
            
            response = requests.get(url, timeout=30, allow_redirects=True)
            load_time = time.time() - start_time
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Basic metrics
            page_size = len(response.content)
            page_size_kb = round(page_size / 1024, 2)
            load_time_ms = round(load_time * 1000, 2)
            
            metrics = {
                "load_time_ms": load_time_ms,
                "page_size_kb": page_size_kb,
                "status_code": response.status_code,
                "redirects": len(response.history),
                "compression": 'gzip' in response.headers.get('content-encoding', '').lower()
            }
            
            # Performance scoring
            if load_time_ms > 3000:
                performance_score -= 30
                issues.append(f"Slow loading time: {load_time_ms}ms")
            elif load_time_ms > 1500:
                performance_score -= 15
                issues.append(f"Moderate loading time: {load_time_ms}ms")
            
            if page_size_kb > 1024:
                performance_score -= 20
                issues.append(f"Large page size: {page_size_kb}KB")
            elif page_size_kb > 512:
                performance_score -= 10
                issues.append(f"Moderate page size: {page_size_kb}KB")
            
            # Count resources
            images = soup.find_all('img')
            scripts = soup.find_all('script')
            stylesheets = soup.find_all('link', rel='stylesheet')
            
            metrics.update({
                "images_count": len(images),
                "scripts_count": len(scripts),
                "stylesheets_count": len(stylesheets)
            })
            
            # Check for optimization issues
            if len(images) > 50:
                performance_score -= 15
                issues.append(f"Too many images: {len(images)}")
            
            if len(scripts) > 20:
                performance_score -= 10
                issues.append(f"Too many scripts: {len(scripts)}")
            
            # Check compression
            if not metrics["compression"]:
                performance_score -= 15
                issues.append("No compression detected")
            
            # Check caching headers
            cache_headers = ['cache-control', 'expires', 'etag', 'last-modified']
            cache_found = any(header in response.headers for header in cache_headers)
            if not cache_found:
                performance_score -= 10
                issues.append("No caching headers found")
            
            return {
                "score": max(0, performance_score),
                "metrics": metrics,
                "issues": issues,
                "grade": self._get_grade(max(0, performance_score))
            }
            
        except Exception as e:
            return {
                "score": 0,
                "error": str(e),
                "grade": "F"
            }
    
    def _analyze_seo(self, url: str) -> Dict:
        """SEO analysis"""
        seo_score = 100
        issues = []
        seo_metrics = {}
        
        try:
            response = requests.get(url, timeout=10)
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Title analysis
            title = soup.find('title')
            if title:
                title_text = title.string.strip() if title.string else ""
                seo_metrics["title"] = title_text
                seo_metrics["title_length"] = len(title_text)
                
                if not title_text:
                    seo_score -= 25
                    issues.append("Missing page title")
                elif len(title_text) > 60:
                    seo_score -= 10
                    issues.append(f"Title too long: {len(title_text)} characters")
                elif len(title_text) < 30:
                    seo_score -= 5
                    issues.append(f"Title too short: {len(title_text)} characters")
            else:
                seo_score -= 25
                issues.append("No title tag found")
            
            # Meta description
            meta_desc = soup.find('meta', attrs={'name': 'description'})
            if meta_desc:
                desc_content = meta_desc.get('content', '').strip()
                seo_metrics["meta_description"] = desc_content
                seo_metrics["meta_description_length"] = len(desc_content)
                
                if not desc_content:
                    seo_score -= 20
                    issues.append("Empty meta description")
                elif len(desc_content) > 160:
                    seo_score -= 5
                    issues.append(f"Meta description too long: {len(desc_content)} characters")
            else:
                seo_score -= 20
                issues.append("Missing meta description")
            
            # Heading structure
            h1_tags = soup.find_all('h1')
            h2_tags = soup.find_all('h2')
            h3_tags = soup.find_all('h3')
            
            seo_metrics.update({
                "h1_count": len(h1_tags),
                "h2_count": len(h2_tags),
                "h3_count": len(h3_tags)
            })
            
            if len(h1_tags) == 0:
                seo_score -= 15
                issues.append("No H1 heading found")
            elif len(h1_tags) > 1:
                seo_score -= 10
                issues.append(f"Multiple H1 headings: {len(h1_tags)}")
            
            # Image alt tags
            images = soup.find_all('img')
            images_without_alt = [img for img in images if not img.get('alt')]
            
            seo_metrics["images_total"] = len(images)
            seo_metrics["images_without_alt"] = len(images_without_alt)
            
            if images and len(images_without_alt) > 0:
                alt_percentage = (len(images_without_alt) / len(images)) * 100
                if alt_percentage > 50:
                    seo_score -= 15
                    issues.append(f"{alt_percentage:.0f}% of images missing alt tags")
                elif alt_percentage > 25:
                    seo_score -= 8
                    issues.append(f"{alt_percentage:.0f}% of images missing alt tags")
            
            # Internal/External links
            links = soup.find_all('a', href=True)
            internal_links = 0
            external_links = 0
            base_domain = urlparse(url).netloc
            
            for link in links:
                href = link.get('href')
                if href:
                    full_url = urljoin(url, href)
                    link_domain = urlparse(full_url).netloc
                    if link_domain == base_domain or not link_domain:
                        internal_links += 1
                    else:
                        external_links += 1
            
            seo_metrics.update({
                "internal_links": internal_links,
                "external_links": external_links,
                "total_links": len(links)
            })
            
            # URL structure
            parsed = urlparse(url)
            if len(parsed.path) > 100:
                seo_score -= 5
                issues.append("URL too long")
            
            # Check for robots.txt
            try:
                robots_response = requests.get(urljoin(url, '/robots.txt'), timeout=5)
                seo_metrics["robots_txt"] = robots_response.status_code == 200
                if robots_response.status_code != 200:
                    seo_score -= 5
                    issues.append("No robots.txt found")
            except:
                seo_metrics["robots_txt"] = False
                seo_score -= 5
                issues.append("Could not access robots.txt")
            
            return {
                "score": max(0, seo_score),
                "metrics": seo_metrics,
                "issues": issues,
                "grade": self._get_grade(max(0, seo_score))
            }
            
        except Exception as e:
            return {
                "score": 0,
                "error": str(e),
                "grade": "F"
            }
    
    def _analyze_accessibility(self, url: str) -> Dict:
        """Accessibility analysis"""
        accessibility_score = 100
        issues = []
        
        try:
            response = requests.get(url, timeout=10)
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Language attribute
            html_tag = soup.find('html')
            if not html_tag or not html_tag.get('lang'):
                accessibility_score -= 15
                issues.append("Missing language attribute")
            
            # Image alt attributes (already checked in SEO, but important for accessibility)
            images = soup.find_all('img')
            images_without_alt = [img for img in images if not img.get('alt')]
            
            if images and len(images_without_alt) > 0:
                alt_percentage = (len(images_without_alt) / len(images)) * 100
                if alt_percentage > 25:
                    accessibility_score -= 20
                    issues.append(f"{alt_percentage:.0f}% of images missing alt text")
            
            # Form labels
            forms = soup.find_all('form')
            form_issues = 0
            for form in forms:
                inputs = form.find_all(['input', 'textarea', 'select'])
                for input_elem in inputs:
                    input_type = input_elem.get('type', 'text')
                    if input_type not in ['hidden', 'submit', 'button']:
                        # Check for associated label
                        input_id = input_elem.get('id')
                        input_name = input_elem.get('name')
                        
                        label_found = False
                        if input_id:
                            label = form.find('label', {'for': input_id})
                            if label:
                                label_found = True
                        
                        # Check for aria-label or title
                        if not label_found and not input_elem.get('aria-label') and not input_elem.get('title'):
                            form_issues += 1
            
            if form_issues > 0:
                accessibility_score -= min(30, form_issues * 10)
                issues.append(f"{form_issues} form inputs without proper labels")
            
            # Heading structure
            headings = soup.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6'])
            if len(headings) == 0:
                accessibility_score -= 15
                issues.append("No heading structure found")
            
            # Check for ARIA landmarks
            landmarks = soup.find_all(attrs={"role": True})
            aria_labels = soup.find_all(attrs={"aria-label": True})
            
            if len(landmarks) == 0 and len(aria_labels) == 0:
                accessibility_score -= 10
                issues.append("No ARIA landmarks or labels found")
            
            # Color contrast (basic check - can't do full analysis without rendering)
            # This is a simplified check
            styles = soup.find_all('style')
            inline_styles = soup.find_all(attrs={"style": True})
            
            color_info = {
                "style_tags": len(styles),
                "inline_styles": len(inline_styles)
            }
            
            return {
                "score": max(0, accessibility_score),
                "issues": issues,
                "color_info": color_info,
                "grade": self._get_grade(max(0, accessibility_score))
            }
            
        except Exception as e:
            return {
                "score": 0,
                "error": str(e),
                "grade": "F"
            }
    
    def _analyze_technical(self, url: str, domain: str) -> Dict:
        """Technical analysis"""
        technical_score = 100
        issues = []
        technical_info = {}
        
        try:
            response = requests.get(url, timeout=10)
            
            # Server information
            technical_info["server"] = response.headers.get('server', 'Unknown')
            technical_info["powered_by"] = response.headers.get('x-powered-by', 'Unknown')
            
            # HTTP version (simplified)
            technical_info["http_version"] = "HTTP/2" if hasattr(response, 'http_version') else "HTTP/1.1"
            
            # DNS information
            try:
                dns_info = {}
                # A records
                try:
                    a_records = dns.resolver.resolve(domain, 'A')
                    dns_info["a_records"] = [str(record) for record in a_records]
                except dns.resolver.NXDOMAIN:
                    dns_info["a_records"] = []
                    issues.append("Domain not found in DNS")
                except dns.resolver.NoAnswer:
                    dns_info["a_records"] = []
                except Exception as dns_error:
                    dns_info["a_records"] = []
                
                # MX records
                try:
                    mx_records = dns.resolver.resolve(domain, 'MX')
                    dns_info["mx_records"] = [f"{record.preference} {record.exchange}" for record in mx_records]
                except (dns.resolver.NXDOMAIN, dns.resolver.NoAnswer):
                    dns_info["mx_records"] = []
                except Exception:
                    dns_info["mx_records"] = []
                
                technical_info["dns"] = dns_info
                
            except Exception as e:
                technical_info["dns_error"] = f"DNS analysis failed: {str(e)[:100]}"
                technical_score -= 5
                issues.append("DNS analysis failed")
            
            # Check for mobile viewport
            soup = BeautifulSoup(response.content, 'html.parser')
            viewport_meta = soup.find('meta', attrs={'name': 'viewport'})
            
            if viewport_meta:
                technical_info["viewport"] = viewport_meta.get('content', '')
                if 'width=device-width' not in technical_info["viewport"]:
                    technical_score -= 15
                    issues.append("Missing responsive viewport configuration")
            else:
                technical_score -= 20
                issues.append("No viewport meta tag found")
            
            # Check for favicon
            favicon_found = bool(soup.find('link', rel=lambda x: x and 'icon' in x.lower()))
            technical_info["favicon"] = favicon_found
            
            if not favicon_found:
                technical_score -= 5
                issues.append("No favicon found")
            
            # Check for structured data
            json_ld = soup.find_all('script', type='application/ld+json')
            microdata = soup.find_all(attrs={"itemtype": True})
            
            technical_info["structured_data"] = {
                "json_ld_count": len(json_ld),
                "microdata_count": len(microdata)
            }
            
            if len(json_ld) == 0 and len(microdata) == 0:
                technical_score -= 10
                issues.append("No structured data found")
            
            return {
                "score": max(0, technical_score),
                "info": technical_info,
                "issues": issues,
                "grade": self._get_grade(max(0, technical_score))
            }
            
        except Exception as e:
            return {
                "score": 0,
                "error": str(e),
                "grade": "F"
            }
    
    def _calculate_overall_score(self, analysis: Dict) -> int:
        """Calculate weighted overall score"""
        weights = {
            "security_analysis": 0.25,  # 25%
            "performance_analysis": 0.25,  # 25%
            "seo_analysis": 0.25,  # 25%
            "accessibility_analysis": 0.15,  # 15%
            "technical_analysis": 0.10  # 10%
        }
        
        total_score = 0
        for category, weight in weights.items():
            if category in analysis and 'score' in analysis[category]:
                total_score += analysis[category]['score'] * weight
        
        return round(total_score)
    
    def _generate_recommendations(self, analysis: Dict) -> List[str]:
        """Generate actionable recommendations"""
        recommendations = []
        
        # Security recommendations
        if analysis.get('security_analysis', {}).get('score', 100) < 80:
            recommendations.append("🔒 Implement HTTPS and security headers")
            recommendations.append("🛡️ Add Content Security Policy (CSP)")
        
        # Performance recommendations
        if analysis.get('performance_analysis', {}).get('score', 100) < 80:
            recommendations.append("⚡ Optimize images and enable compression")
            recommendations.append("🚀 Minimize HTTP requests and use caching")
        
        # SEO recommendations
        if analysis.get('seo_analysis', {}).get('score', 100) < 80:
            recommendations.append("📈 Optimize title tags and meta descriptions")
            recommendations.append("🏷️ Add alt tags to all images")
        
        # Accessibility recommendations
        if analysis.get('accessibility_analysis', {}).get('score', 100) < 80:
            recommendations.append("♿ Improve accessibility with proper labels and ARIA")
            recommendations.append("🎨 Ensure sufficient color contrast")
        
        # Technical recommendations
        if analysis.get('technical_analysis', {}).get('score', 100) < 80:
            recommendations.append("📱 Add responsive design viewport meta tag")
            recommendations.append("📊 Implement structured data markup")
        
        return recommendations
    
    def _get_grade(self, score: int) -> str:
        """Convert score to letter grade"""
        if score >= 90:
            return "A"
        elif score >= 80:
            return "B"
        elif score >= 70:
            return "C"
        elif score >= 60:
            return "D"
        else:
            return "F"
