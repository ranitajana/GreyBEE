# GreyBot

GreyBot is an AI agent designed for the Bluesky platform that identifies the most trending topics in the AI sector. It automatically generates and posts a thread every 30 minutes to keep users informed about the latest developments. Additionally, GreyBot engages with users by responding to any mentions within one minute, ensuring timely interaction and fostering community engagement.

## Installation

To get started with this project, you'll need to install the required dependencies listed in the `requirements.txt` file. Follow these steps:

1. **Clone the repository**:
```bash
git@github.com:ranitajana/GreyBot.git
cd GreyBot
```
Set up a virtual environment (optional but recommended):
If you want to keep your project dependencies isolated, you can create a virtual environment:
```bash
python -m venv venv
```
Activate the virtual environment:
On Windows:
```bash
venv\Scripts\activate
```
On macOS/Linux:
```bash
source venv/bin/activate
```
Install the required packages:
Use pip to install the dependencies from requirements.txt:
```bash
pip install -r requirements.txt
```
Usage
Once you have installed the necessary packages, you can run the code using the following command:
```bash
python post_reply.py
```
