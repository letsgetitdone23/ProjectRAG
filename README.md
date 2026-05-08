# Nippon India Mutual Fund RAG System

A complete end-to-end Retrieval-Augmented Generation (RAG) platform to answer queries related to Nippon India Mutual Funds, built with modern AI, backend, and frontend technologies. 

## 🏗️ Architecture Overview

This project consists of three main components:
1. **Data Ingestion & Processing Pipeline**: Automated data scraping, cleaning, chunking, and generation of embeddings using `BAAI/bge-large-en-v1.5`. Data is periodically refreshed and synchronized using scheduled GitHub Actions.
2. **Backend API (FastAPI)**: A highly concurrent, multi-threaded FastAPI server that performs vector searches against a local SQLite/Chroma Vector database and utilizes advanced LLMs for context-aware, accurate answers.
3. **Frontend Application (Next.js)**: A sleek and responsive user interface built with Next.js and Tailwind CSS, allowing users to converse seamlessly with the AI FAQ assistant.

## 🚀 Tech Stack
- **AI/ML**: LangChain, ChromaDB, Hugging Face (`BGE Embeddings`), Groq (LLM Inference)
- **Backend**: Python 3.11, FastAPI, Uvicorn, SQLite
- **Frontend**: Next.js 16 (React), Tailwind CSS
- **CI/CD & Deployment**: GitHub Actions, Render (Backend), Vercel (Frontend)

## 📁 Project Structure

- `/src`: Core backend logic (APIs, LLM clients, chunking, retrieval, storage).
- `/scripts`: Standalone Python scripts for data extraction, processing, health checks, and scheduled syncs.
- `/docs`: Detailed project documentation, including architecture schemas and deployment plans.
- `/config`: YAML configurations for the scraper, groq, chunking, and schemas.
- `/nippon-india-frontend`: The primary Next.js frontend application.
- `/.github/workflows`: Automated GitHub Actions pipelines for deployment and daily data refreshes.

## 🛠️ Local Development Setup

### 1. Clone the repository
```bash
git clone https://github.com/letsgetitdone23/ProjectRAG.git
cd ProjectRAG
```

### 2. Set up Backend
```bash
# Create a virtual environment and install dependencies
python -m venv venv
# On Windows use: venv\Scripts\activate
# On Mac/Linux use: source venv/bin/activate
pip install -r requirements.txt

# Configure environment variables
cp .env.example .env
# Edit .env with your specific API keys (Groq, HuggingFace, etc.)

# Ensure proper encoding on Windows
set PYTHONIOENCODING=utf-8

# Start the FastAPI server (Runs on http://localhost:8000)
python src/api/multi_threaded_api_gateway.py
```

### 3. Set up Frontend
```bash
cd nippon-india-frontend

# Install node dependencies
npm install

# Start the development server (Runs on http://localhost:3000)
npm run dev
```

## 🔄 Automated CI/CD
This repository includes automated pipelines:
- **Daily Data Refresh**: Automatically scrapes new data, updates the vector databases, and refreshes embeddings every day.
- **Continuous Deployment**: Any push to the `main` branch automatically triggers backend deployment to Render and frontend deployment to Vercel (requires configured repository secrets like `VERCEL_TOKEN`, `RENDER_DEPLOY_HOOK`).

## 📄 Documentation
For more in-depth technical details, refer to the documents inside the `/docs` folder:
- [RAG Architecture Plan](docs/rag_architecture.md)
- [Chunking & Embedding Architecture](docs/chunking_embedding_architecture.md)
- [Deployment Plan](docs/deployment_plan.md)
