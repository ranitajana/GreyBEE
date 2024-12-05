import os
import sys
import time
import schedule
from scraper.twitter_scraper import Twitter_Scraper

try:
    from dotenv import load_dotenv
    print("Loading .env file")
    load_dotenv()
    print("Loaded .env file\n")
except Exception as e:
    print(f"Error loading .env file: {e}")
    sys.exit(1)

def main():
    print("Starting Twitter Scraper...")
    
    # Initialize scraper once
    scraper = Twitter_Scraper(
        mail=os.getenv("TWITTER_MAIL"),
        username=os.getenv("TWITTER_USERNAME"),
        password=os.getenv("TWITTER_PASSWORD"),
        openai_key=os.getenv("OPENAI_API_KEY")
    )
    
    # Initial login and start monitoring mentions
    scraper.login()
    scraper.start_monitoring_mentions()
    
    print("\nScheduler started. Press Ctrl+C to exit.")
    
    try:
        while True:
            schedule.run_pending()
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nScraper stopped by user")
        scraper.driver.quit()
        sys.exit(0) 

if __name__ == "__main__":
    main()

