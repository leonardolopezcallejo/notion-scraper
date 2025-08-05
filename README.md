# 🧠 AI Notion Assistant by Garaje

This project extracts structured text from a Notion page, indexes it in Azure Cognitive Search, and enables question-answering via Azure OpenAI (RAG: Retrieval-Augmented Generation).

## 🛠️ Technology

- Python (scripts only, no web server)
- Notion API (via `notion-client`)
- Azure Cognitive Search
- Azure OpenAI API
- `.env` for secret management

## 📂 Structure

- `notion_scraper.py`: reads Notion blocks and saves raw content.
- `ask_with_rag_notion.py`: chunks and uploads data into Azure Search.
- `preguntar_con_rag.py`: interactive CLI to ask questions using RAG.
- `app_api.py`: server that gets the request from web and launches functions

## 🚀 How to Run the POC (from PowerShell)

### 0. Install Python and pip
```bash
winget install --id Python.Python.3 --source winget
python --version
pip --version
```

### 1. Clone the repository
```bash
git clone https://github.com/leonardolopezcallejo/notion-scraper.git
cd notion-scraper
```

### 2. Create virtual environment and install dependencies
```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

### 3. Set environment variables
```bash
NOTION_TOKEN="ntn_..."
PAGE_ID="..."

AZURE_SEARCH_ENDPOINT="https://<search_endpoint>.search.windows.net"
AZURE_SEARCH_KEY="..."
AZURE_SEARCH_NOTION_INDEX="notion-index"

AZURE_OPENAI_ENDPOINT="https://<deployment_name>.openai.azure.com/"
AZURE_OPENAI_KEY="..."
AZURE_OPENAI_DEPLOYMENT="gpt-35-turbo"
```

### 4. Run the scripts to scrap and create index (repeat after important updates in notion)
```bash
python -m app.notion_scraper
python upload_to_azure_search_notion.py
```

### 5. Open the HTML and run the app
```bash
start .\static\index.html
uvicorn app.app_api:app --reload --port 8002
```