# app/services/health.py
import time
import requests

def verify_application_heartbeat(target_url: str, max_retries: int = 5, delay_seconds: int = 5) -> bool:
    """
    Pings the deployment target application's health endpoint.
    Returns True if the server wakes up and returns a 200 OK status.
    """
    health_endpoint = f"{target_url.rstrip('/')}/health"
    
    for attempt in range(1, max_retries + 1):
        try:
            # Send an HTTP GET with a short timeout constraint
            response = requests.get(health_endpoint, timeout=3)
            if response.status_code == 200:
                return True
        except requests.RequestException:
            # App is still booting up or DNS is propagating, ignore exception and retry
            pass
        
        time.sleep(delay_seconds)
        
    return False