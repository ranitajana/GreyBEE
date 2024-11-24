import requests

# Replace 'YOUR_API_TOKEN' with your actual Bright Data API token
api_token = '90bada4c79000883cfebc7d5e1bc075b42f141c3bee9c696e05967bfffce4431'
url = "https://api.brightdata.com/datasets/v3/trigger?dataset_id=YOUR_DATASET_ID&format=json"

# Define the query for tweets mentioning @GreyBotAI
query = {
    "query": "@GreyBotAI",
    "limit": 10  # Number of tweets to fetch
}

headers = {
    "Authorization": f"Bearer {api_token}",
    "Content-Type": "application/json"
}

response = requests.post(url, json=query, headers=headers)

if response.status_code == 200:
    tweets = response.json()
    for tweet in tweets['data']:
        print(f"User: {tweet['username']}, Tweet: {tweet['description']}, Date: {tweet['date']}")
else:
    print(f"Failed to fetch data: {response.status_code}, {response.text}")