# GreyBEE

GreyBEE is an AI agent designed for the Bluesky platform that identifies the most trending topics in the AI sector. It automatically generates and posts a thread every 30 minutes to keep users informed about the latest developments. Additionally, GreyBot engages with users by responding to any mentions within one minute, ensuring timely interaction and fostering community engagement.

## Key Features of GreyBEE
`Trending Topic Identification:` GreyBEE continuously monitors the AI landscape to identify the most trending topics. It ensures users are kept up-to-date with the latest developments in artificial intelligence.

`Automated Thread Generation:` Every 45 minutes, GreyBEE automatically generates and posts a new thread based on viral posts on the platform. Every 2 hours GreyBEE posts thread about recent AI news. 

`User Engagement:` GreyBEE is programmed to respond to user mentions/comment within one minute. This quick interaction fosters community engagement and encourages discussions around AI topics.

`Fact-Checking and Summarization:` Users can tag GreyBEE with #factcheck or #summarise to prompt it to verify facts or summarize content from posts, enhancing the reliability of information shared on the platform.

## How to Interact with GreyBEE
To try out GreyBEE, users need to sign up for Bluesky and can find it at the profile link.
Tagging @greybe.blusky.social in posts will elicit a response from GreyBEE within one minute, making it easy for users to engage with the AI directly.
Utilizing hashtags like #factcheck or #summarise further enhances the interaction by allowing users to seek clarification or concise information on specific topics.

## Installation

To get started with this project, you'll need to install the required dependencies listed in the `requirements.txt` file. Follow these steps:

**Clone the repository**:

```bash
git@github.com:ranitajana/GreyBEE.git
cd GreyBEE/grey-fastapi2/
```
**Set up a virtual environment (optional but recommended)**:

If you want to keep your project dependencies isolated, you can create a virtual environment:
```bash
python -m venv venv
```
**Activate the virtual environment:**

On Windows:
```bash
venv\Scripts\activate
```
On macOS/Linux:
```bash
source venv/bin/activate
```
**Install the required packages:**

Use pip to install the dependencies from requirements.txt:
```bash
pip install -r requirements.txt
```
**Create a .env file with credentials:**

```bash
BSKY_IDENTIFIER=xxxx
BSKY_PASSWORD=xxxx
OPENAI_API_KEY=xxxx
PINECONE_API_KEY=xxxx
```
**Usage**

Once you have installed the necessary packages, you can run the code using the following command:
```bash
python main.py
```
