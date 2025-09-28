"""
API Usage Optimization and Caching System
Reduces GroqCloud API calls by caching results and implementing smart fallbacks
"""

import hashlib
import json
import os
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
import pickle
import time

class APIOptimizer:
    """Optimize API usage through caching, rate limiting, and smart fallbacks"""
    
    def __init__(self, cache_dir: str = "data/cache"):
        self.cache_dir = cache_dir
        os.makedirs(cache_dir, exist_ok=True)
        self.cache_duration = timedelta(hours=2)  # Extended cache for rate limit relief
        self.last_api_call = 0
        self.min_call_interval = 2  # Minimum 2 seconds between API calls
    
    def _get_cache_key(self, email_content: str, analysis_type: str = "sentiment") -> str:
        """Generate cache key from email content"""
        content_hash = hashlib.md5(email_content.encode()).hexdigest()
        return f"{analysis_type}_{content_hash}"
    
    def _get_cache_path(self, cache_key: str) -> str:
        """Get file path for cached result"""
        return os.path.join(self.cache_dir, f"{cache_key}.json")
    
    def get_cached_result(self, email_content: str, analysis_type: str = "sentiment") -> Optional[Dict[str, Any]]:
        """Retrieve cached analysis result if available and not expired"""
        try:
            cache_key = self._get_cache_key(email_content, analysis_type)
            cache_path = self._get_cache_path(cache_key)
            
            if not os.path.exists(cache_path):
                return None
            
            with open(cache_path, 'r') as f:
                cached_data = json.load(f)
            
            # Check if cache is still valid
            cached_time = datetime.fromisoformat(cached_data['timestamp'])
            if datetime.now() - cached_time > self.cache_duration:
                os.remove(cache_path)  # Remove expired cache
                return None
            
            print(f"🎯 Using cached result (saved API call)")
            return cached_data['result']
        
        except Exception as e:
            print(f"⚠️ Cache read error: {e}")
            return None
    
    def cache_result(self, email_content: str, result: Dict[str, Any], analysis_type: str = "sentiment"):
        """Cache analysis result for future use"""
        try:
            cache_key = self._get_cache_key(email_content, analysis_type)
            cache_path = self._get_cache_path(cache_key)
            
            cached_data = {
                'timestamp': datetime.now().isoformat(),
                'result': result,
                'email_length': len(email_content)
            }
            
            with open(cache_path, 'w') as f:
                json.dump(cached_data, f)
            
            print(f"💾 Cached result for future use")
        
        except Exception as e:
            print(f"⚠️ Cache write error: {e}")
    
    def should_use_fallback(self, email_content: str) -> bool:
        """Determine if we should use fallback analysis instead of AI (enhanced for rate limits)"""
        # ALWAYS use fallback if we're hitting rate limits
        current_time = time.time()
        if current_time - self.last_api_call < self.min_call_interval:
            print(f"🛑 Rate limit protection: Using fallback to avoid API limits")
            return True
            
        # Use fallback for very short or very simple emails
        if len(email_content) < 50:
            return True
        
        # Use fallback if email contains clear buying signals (often more accurate anyway)
        strong_signals = ['budget approved', 'demo', 'asap', 'urgent', 'help us', 'need replacement', 
                         'this week', 'crashing', 'losing productivity', 'schedule demo', 'book demo']
        signal_count = sum(signal in email_content.lower() for signal in strong_signals)
        
        if signal_count >= 2:
            print(f"🚀 Using optimized fallback ({signal_count} strong buying signals detected)")
            return True
        
        # Use fallback for obvious negative cases
        negative_signals = ['not interested', 'no thanks', 'found alternative', 'unsubscribe']
        if any(signal in email_content.lower() for signal in negative_signals):
            print(f"🚀 Using optimized fallback (clear negative signals)")
            return True
        
        return False
    
    def record_api_call(self):
        """Record that an API call was made for rate limiting"""
        self.last_api_call = time.time()
    
    def get_usage_stats(self) -> Dict[str, Any]:
        """Get API usage statistics"""
        cache_files = [f for f in os.listdir(self.cache_dir) if f.endswith('.json')]
        
        return {
            'cached_analyses': len(cache_files),
            'estimated_api_calls_saved': len(cache_files),
            'cache_directory': self.cache_dir
        }

# Global optimizer instance
api_optimizer = APIOptimizer()
