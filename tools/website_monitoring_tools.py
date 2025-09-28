import requests
from bs4 import BeautifulSoup
from crewai.tools import BaseTool
from pydantic import BaseModel, Field
from typing import Type
import json
import hashlib
from urllib.parse import urljoin, urlparse
import os
import time

class WebsiteMonitoringInput(BaseModel):
    url: str = Field(..., description="Website URL to monitor")

class WebsiteContentFetcher(BaseTool):
    name: str = "website_content_fetcher"
    description: str = "Fetches and analyzes website content for changes"
    args_schema: Type[BaseModel] = WebsiteMonitoringInput
    
    def _run(self, url: str) -> str:
        try:
            # Fetch website content
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            
            # Parse HTML content
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Extract key elements
            result = {
                "url": url,
                "status_code": response.status_code,
                "title": soup.title.string if soup.title else "",
                "meta_description": "",
                "h1_tags": [h1.get_text().strip() for h1 in soup.find_all('h1')],
                "h2_tags": [h2.get_text().strip() for h2 in soup.find_all('h2')[:10]],  # Add H2 tags
                "nav_links": [],
                "images_count": len(soup.find_all('img')),
                "forms_count": len(soup.find_all('form')),
                "external_links_count": 0,
                "internal_links_count": 0,
                "content_hash": hashlib.md5(response.content).hexdigest(),
                "word_count": len(soup.get_text().split()),
                "page_size_kb": round(len(response.content) / 1024, 2),
                "load_time_ms": round(response.elapsed.total_seconds() * 1000, 2),
                "timestamp": time.time()
            }
            
            # Get meta description
            meta_desc = soup.find('meta', attrs={'name': 'description'})
            if meta_desc:
                result["meta_description"] = meta_desc.get('content', '')
            
            # Extract navigation links and analyze them
            nav_links = []
            external_links = 0
            internal_links = 0
            base_domain = urlparse(url).netloc
            
            for link in soup.find_all('a', href=True)[:20]:  # Limit to first 20 links for nav_links
                href = link.get('href')
                text = link.get_text().strip()
                if href and text:
                    full_url = urljoin(url, href)
                    nav_links.append({"text": text, "url": full_url})
                    
                    # Count internal vs external links
                    link_domain = urlparse(full_url).netloc
                    if link_domain == base_domain or not link_domain:
                        internal_links += 1
                    else:
                        external_links += 1
            
            # Count all links for statistics
            all_links = soup.find_all('a', href=True)
            for link in all_links[20:]:  # Count remaining links
                href = link.get('href')
                if href:
                    full_url = urljoin(url, href)
                    link_domain = urlparse(full_url).netloc
                    if link_domain == base_domain or not link_domain:
                        internal_links += 1
                    else:
                        external_links += 1
                        
            result["nav_links"] = nav_links
            result["external_links_count"] = external_links
            result["internal_links_count"] = internal_links
            
            return json.dumps(result, indent=2)
            
        except Exception as e:
            return json.dumps({
                "url": url,
                "error": str(e),
                "timestamp": time.time(),
                "status": "failed"
            })

class ChangeDetectionTool(BaseTool):
    name: str = "change_detection_tool"
    description: str = "Compares current website content with previous snapshot"
    args_schema: Type[BaseModel] = WebsiteMonitoringInput
    
    def _run(self, url: str) -> str:
        try:
            # Create data directory if it doesn't exist
            os.makedirs('data/snapshots', exist_ok=True)
            
            # Generate filename from URL
            url_hash = hashlib.md5(url.encode()).hexdigest()
            snapshot_file = f'data/snapshots/{url_hash}.json'
            
            # Get current content
            fetcher = WebsiteContentFetcher()
            current_data = json.loads(fetcher._run(url))
            
            # Compare with previous snapshot
            changes_detected = []
            
            if os.path.exists(snapshot_file):
                with open(snapshot_file, 'r') as f:
                    previous_data = json.load(f)
                
                # Compare key elements
                if current_data.get('title') != previous_data.get('title'):
                    changes_detected.append({
                        "type": "title_change",
                        "old": previous_data.get('title'),
                        "new": current_data.get('title'),
                        "significance": 8
                    })
                
                if current_data.get('meta_description') != previous_data.get('meta_description'):
                    changes_detected.append({
                        "type": "meta_description_change", 
                        "old": previous_data.get('meta_description'),
                        "new": current_data.get('meta_description'),
                        "significance": 6
                    })
                
                # Check for new H1 tags
                old_h1s = set(previous_data.get('h1_tags', []))
                new_h1s = set(current_data.get('h1_tags', []))
                
                if new_h1s != old_h1s:
                    added_h1s = new_h1s - old_h1s
                    removed_h1s = old_h1s - new_h1s
                    
                    if added_h1s or removed_h1s:
                        changes_detected.append({
                            "type": "heading_changes",
                            "added": list(added_h1s),
                            "removed": list(removed_h1s),
                            "significance": 7
                        })
                
                # Check content hash
                if current_data.get('content_hash') != previous_data.get('content_hash'):
                    changes_detected.append({
                        "type": "content_change",
                        "description": "Overall page content has changed",
                        "significance": 5
                    })
            else:
                changes_detected.append({
                    "type": "first_snapshot",
                    "description": "Initial website snapshot created",
                    "significance": 1
                })
            
            # Save current snapshot
            with open(snapshot_file, 'w') as f:
                json.dump(current_data, f, indent=2)
            
            result = {
                "url": url,
                "changes_detected": changes_detected,
                "total_changes": len(changes_detected),
                "max_significance": max([c.get('significance', 0) for c in changes_detected]) if changes_detected else 0,
                "timestamp": time.time()
            }
            
            return json.dumps(result, indent=2)
            
        except Exception as e:
            return json.dumps({
                "url": url,
                "error": str(e),
                "status": "failed"
            })
