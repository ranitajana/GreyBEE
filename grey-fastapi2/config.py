from datetime import time
import pytz

# Define time intervals for posting and checking mentions/notifications

MEMORY_UPDATE_TIME = time(hour=3, minute=11)  # 2:35 AM IST
MEMORY_UPDATE_TIMEZONE = pytz.timezone('Asia/Kolkata')  # IST timezone 
THREAD_POST_INTERVAL = 2700  # 45 minutes in seconds
CHECK_INTERVAL = 60  # 1 minute in seconds
NEWS_POST_INTERVAL = 7200  # 2 hours in seconds
MEME_ENGAGEMENT_INTERVAL = 2400  # 30 minutes

# # Define memory update interval
#     MEMORY_UPDATE_INTERVAL = 86400  # 24 hours in seconds (24 * 60 * 60)
#     MEMORY_RETENTION_PERIOD = 1 

# List of keywords to search for viral posts on Artificial Intelligence
keywords = [
    # General AI Concepts
    "artificial intelligence", "machine learning", "deep learning", "neural networks", "natural language processing",
    
    # AI Applications
    "computer vision", "speech recognition", "robotics", "autonomous vehicles", "AI in healthcare",
    
    # Ethical Considerations
    "AI ethics", "bias in AI", "transparency", "accountability", "privacy concerns",
    
    # AI Technologies
    "reinforcement learning", "supervised learning", "unsupervised learning", "generative adversarial networks", "edge computing",
    
    # Industry Impact
    "AI in business", "AI in finance", "AI in education", "AI in marketing", "AI and job displacement",
    
    # AI Research and Development
    "AI algorithms", "data science", "big data", "cloud computing", "quantum computing",
    
    # Future of AI
    "singularity", "AGI (Artificial General Intelligence)", "AI governance", "human-AI collaboration", "future of work",
    
    # AI Trends
    "AI startups", "AI funding", "AI conferences", "open-source AI", "AI regulations"
    ]