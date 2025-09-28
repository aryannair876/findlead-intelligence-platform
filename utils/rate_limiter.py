"""
Rate limiter for Groq API calls
Prevents hitting rate limits by controlling API call frequency
"""
import time
import threading
from datetime import datetime, timedelta

class GroqRateLimiter:
    def __init__(self, calls_per_minute=60, calls_per_day=14400):
        """
        Initialize rate limiter for Groq API
        Default limits: 60 calls/minute, 14400 calls/day for free tier
        """
        self.calls_per_minute = calls_per_minute
        self.calls_per_day = calls_per_day
        self.call_times = []
        self.daily_calls = 0
        self.last_reset = datetime.now()
        self.lock = threading.Lock()
    
    def can_make_call(self):
        """Check if we can make a call without hitting rate limits"""
        with self.lock:
            now = datetime.now()
            
            # Reset daily counter if it's a new day
            if now.date() > self.last_reset.date():
                self.daily_calls = 0
                self.last_reset = now
            
            # Check daily limit
            if self.daily_calls >= self.calls_per_day:
                return False, f"Daily limit reached ({self.calls_per_day} calls)"
            
            # Remove calls older than 1 minute
            minute_ago = now - timedelta(minutes=1)
            self.call_times = [call_time for call_time in self.call_times if call_time > minute_ago]
            
            # Check per-minute limit
            if len(self.call_times) >= self.calls_per_minute:
                oldest_call = min(self.call_times)
                wait_time = (oldest_call + timedelta(minutes=1) - now).total_seconds()
                return False, f"Rate limit reached. Wait {wait_time:.1f} seconds"
            
            return True, "OK"
    
    def record_call(self):
        """Record that we made an API call"""
        with self.lock:
            now = datetime.now()
            self.call_times.append(now)
            self.daily_calls += 1
    
    def wait_if_needed(self):
        """Wait if necessary before making a call"""
        can_call, message = self.can_make_call()
        if not can_call:
            if "Wait" in message:
                wait_time = float(message.split()[-2])
                print(f"⏳ Rate limit: waiting {wait_time:.1f} seconds...")
                time.sleep(wait_time + 1)  # Add 1 second buffer
                return self.wait_if_needed()  # Check again after waiting
            else:
                raise Exception(f"Rate limit exceeded: {message}")
        
        self.record_call()
        return True

# Global rate limiter instance
groq_rate_limiter = GroqRateLimiter()
