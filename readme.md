# 🧠 AI Human-in-the-Loop System

This project implements an **AI-powered human-in-the-loop system** that allows AI to automatically respond to customer queries and escalate to a human supervisor when needed.  
Supervisor responses are stored in **AWS DynamoDB (Local)**, enabling the AI to learn and handle similar queries automatically in the future.

---

##  Features

- Flask-based backend (Python)
- Local DynamoDB integration using Docker
- Human-in-the-loop learning mechanism
- Persistent knowledge base
- Local-only setup (no frontend required)

---

##  Tech Stack

| Component | Technology |
|------------|-------------|
| Backend | Python (Flask) |
| Database | DynamoDB Local (via Docker) |
| Language | Python 3.9+ |
| AWS CLI | Configured for local DynamoDB |

---

##  Installation and Setup

### 1️⃣ Clone the Repository

```bash
git clone https://github.com/your-username/AI-human-loop.git
cd AI-human-loop


### 2️⃣ Set Up Virtual Environment
python -m venv venv
venv\Scripts\activate      # On Windows
# or
source venv/bin/activate   # On macOS/Linux


### 3️⃣ Install Dependencies

pip install -r requirements.txt


### 4️⃣ Run DynamoDB Local

docker pull amazon/dynamodb-local
docker run -d -p 8000:8000 --name dynamodb_local amazon/dynamodb-local
docker ps   # verify container is running


### 5️⃣ AWS CLI Configuration (Local)

aws configure
Use dummy credentials (local DynamoDB doesn’t require real AWS credentials):


### 6️⃣ Setup DynamoDB Tables

python dynamo_setup.py
aws dynamodb list-tables --endpoint-url http://localhost:8000


Expected output:

{ "TableNames": ["HelpRequests", "KnowledgeBase"] }

▶️ Running the Flask App
python app.py