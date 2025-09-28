"""
Singleton crew manager to prevent multiple crew instances
and implement proper rate limiting
"""
from crew import OptimizedIntelligenceCrew
import time
from threading import Lock

class CrewManager:
    _instance = None
    _lock = Lock()
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super(CrewManager, cls).__new__(cls)
                    cls._instance.crew = None
                    cls._instance.last_call_time = 0
                    cls._instance.min_interval = 2  # Minimum 2 seconds between calls
        return cls._instance
    
    def get_crew(self):
        """Get crew instance with rate limiting"""
        current_time = time.time()
        
        # Ensure minimum interval between crew operations
        time_since_last = current_time - self.last_call_time
        if time_since_last < self.min_interval:
            wait_time = self.min_interval - time_since_last
            print(f"⏳ Waiting {wait_time:.1f}s to prevent rate limiting...")
            time.sleep(wait_time)
        
        # Create crew if it doesn't exist
        if self.crew is None:
            print("🚀 Initializing new crew instance...")
            self.crew = OptimizedIntelligenceCrew()
        
        self.last_call_time = time.time()
        return self.crew

# Global crew manager instance
crew_manager = CrewManager()
