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

def scrape_tweets(scraper):
    try:
        # Define your arguments here
        args = {
            "tweets": 10,
            # "hashtag": "AI",
            "latest": True,
            "top": True,
            # "username": "@elonmusk", # username to scrape from
            # "query": "AI", # search query
            "query": "(@GreyBotAI)" # search query with mention
        }

        scraper.scrape_tweets(
            max_tweets=args["tweets"],
            # scrape_hashtag=args["hashtag"],
            scrape_latest=args["latest"],
            scrape_top=args["top"],
            # scrape_username=args["username"],
            scrape_query=args["query"]
        )
        
        print(f"Number of tweets collected: {len(scraper.data)}")
        scraper.save_to_csv()
        
        return True

    except Exception as e:
        print(f"Error: {e}")
        return False

def main():
    print("Starting Twitter Scraper...")
    
    # Initialize scraper once
    scraper = Twitter_Scraper(
        mail=os.getenv("TWITTER_MAIL"),
        username=os.getenv("TWITTER_USERNAME"),
        password=os.getenv("TWITTER_PASSWORD"),
    )
    
    # Initial login
    scraper.login()
    
    # First run
    scrape_tweets(scraper)
    
    # Schedule subsequent runs every 5 minutes reusing the same scraper instance
    schedule.every(5).minutes.do(scrape_tweets, scraper=scraper)
    
    print("\nScheduler started. Press Ctrl+C to exit.")
    
    try:
        while True:
            schedule.run_pending()
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nScraper stopped by user")
        scraper.driver.quit()  # Clean up the WebDriver when stopping
        sys.exit(0)

if __name__ == "__main__":
    main()

