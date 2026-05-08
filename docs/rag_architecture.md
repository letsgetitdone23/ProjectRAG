# Phase-wise RAG Architecture for Mutual Fund FAQ Assistant

## Overview
This document outlines the comprehensive Retrieval-Augmented Generation (RAG) architecture for building a facts-only mutual fund FAQ assistant. The architecture is designed to meet strict compliance requirements while delivering accurate, source-backed responses.

---

## Phase 1: Data Collection & Corpus Preparation

### 1.1 Source Identification
- **Primary Sources**: Nippon India Mutual Funds (AMC), AMFI, SEBI
- **Selected Schemes**: 
  - Nippon India Large Cap Fund
  - Nippon India Flexi Cap Fund  
  - Nippon India Multi Asset Allocation Fund
- **Document Types**: 
  - Scheme Factsheets
  - Key Information Memorandum (KIM)
  - Scheme Information Document (SID)
  - AMC FAQ/Help pages
  - AMFI/SEBI guidance pages
  - Tax document guides

### 1.2 Specific Data Sources
**AMC Primary Sources**:
- Nippon India Mutual Funds AMC Page: https://groww.in/mutual-funds/amc/nippon-india-mutual-funds
- Scheme Pages (Groww):
  - https://groww.in/mutual-funds/nippon-india-large-cap-fund-direct-growth
  - https://groww.in/mutual-funds/nippon-india-flexi-cap-fund-direct-growth
  - https://groww.in/mutual-funds/nippon-india-multi-asset-allocation-fund-direct-growth

**Official AMC Documents (PDFs)**:
- Large Cap Fund SID: https://mf.nipponindiaim.com/InvestorServices/SIDEquity/NipponIndia-Large-Cap-Fund.pdf
- Flexi Cap Fund SID: https://mf.nipponindiaim.com/campaigns/NipponIndiaFlexiCapFund/pdf/Nippon-India-Flexicap-Fund-SID.pdf
- Multi Asset Allocation Fund SID: https://mf.nipponindiaim.com/InvestorServices/SIDEquity/SID-NipponIndia-Multi-Asset-Allocation-Fund.pdf

**AMC Performance Pages**:
- Large Cap Fund: https://mf.nipponindiaim.com/FundsAndPerformance/Pages/NipponIndia-Large-Cap-Fund.aspx
- Flexi Cap Fund: https://mf.nipponindiaim.com/FundsAndPerformance/Pages/NipponIndia-Flexi-Cap-Fund.aspx
- Multi Asset Allocation Fund: https://mf.nipponindiaim.com/FundsAndPerformance/Pages/NipponIndia-Multi-Asset-Allocation-Fund.aspx

**Regulatory Sources**:
- SEBI Fund Details: https://www.sebi.gov.in/sebiweb/other/OtherAction.do?doGetFundDetails=yes&mfId=46&type=2
- AMFI Fund Performance: https://www.amfiindia.com/otherdata/fund-performance

### 1.3 Automated Data Refresh Scheduler
```
Daily 9:30 AM IST → URL Validation → Scraping Service → Processing Pipeline → Vector Store Update
```

**Scheduler Configuration**:
- **Trigger Time**: 9:30 AM IST daily (synchronized with market opening)
- **Timezone**: Asia/Kolkata (UTC+5:30)
- **Platform**: GitHub Actions Workflow
- **Retry Logic**: 3 attempts with 15-minute intervals on failure
- **Monitoring**: Alert on scraping failures or data anomalies
- **Backup Schedule**: Manual workflow dispatch available for immediate updates

**GitHub Actions Components**:
- **Workflow File**: `.github/workflows/data-refresh.yml`
- **Scheduled Trigger**: `cron: '30 9 * * *'` (daily at 9:30 AM IST)
- **Manual Trigger**: `workflow_dispatch` for on-demand updates
- **Secret Management**: GitHub Secrets for API keys and credentials
- **Artifact Storage**: Temporary storage for processed data
- **Environment Variables**: Configuration for different deployment stages

**GitHub Actions Workflow Structure**:
```yaml
name: Daily Data Refresh
on:
  schedule:
    - cron: '30 4 * * *'  # 9:30 AM IST = 4:00 AM UTC
  workflow_dispatch:
    inputs:
      force_update:
        description: 'Force update all sources'
        required: false
        default: false

jobs:
  scrape-and-process:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout repository
        uses: actions/checkout@v3
      
      - name: Setup Python environment
        uses: actions/setup-python@v4
        with:
          python-version: '3.9'
      
      - name: Install dependencies
        run: |
          pip install -r requirements.txt
      
      - name: Run scraping service
        env:
          SEBI_API_KEY: ${{ secrets.SEBI_API_KEY }}
          AMFI_API_KEY: ${{ secrets.AMFI_API_KEY }}
        run: python scripts/scrape_data.py
      
      - name: Process and chunk data
        run: python scripts/process_chunks.py
      
      - name: Generate embeddings
        run: python scripts/generate_embeddings.py
      
      - name: Update vector store
        env:
          PINECONE_API_KEY: ${{ secrets.PINECONE_API_KEY }}
        run: python scripts/update_vector_store.py
      
      - name: Notify on completion
        if: always()
        run: python scripts/notify_completion.py
```

### 1.4 Scraping Service Architecture
```
URL Discovery → Content Extraction → Text Cleaning → Metadata Extraction → Storage
```

**Scraping Components**:

**URL Manager**:
- **URL Validator**: Checks accessibility and response codes
- **Rate Limiter**: Respects robots.txt and implements delays
- **Session Manager**: Handles authentication and cookies
- **Proxy Rotation**: Prevents IP blocking for frequent requests

**Content Extractors**:
- **HTML Scraper**: BeautifulSoup/Scrapy for web pages
- **PDF Parser**: PyPDF2/pdfplumber for document extraction
- **Text Cleaner**: Removes navigation, ads, and irrelevant content
- **Structure Preserver**: Maintains headings, tables, and lists

**Data Processors**:
- **Metadata Extractor**: Captures source URL, timestamp, document type
- **Content Validator**: Ensures facts-only compliance
- **Duplicate Detector**: Identifies and removes redundant content
- **Change Detector**: Compares with previous versions for updates

**Source-Specific Handlers**:
- **AMC Official Pages**: Handles dynamic content and JavaScript
- **PDF Documents**: Extracts text from SIDs and factsheets
- **Performance Pages**: Captures tabular data and charts
- **Regulatory Sites**: Handles complex government website structures

### 1.5 Document Processing
- **Text Normalization**: Standardize formatting, remove irrelevant content
- **Chunking Strategy**: Semantic chunking (200-500 tokens) with overlap
- **Metadata Enrichment**: Add source URL, document type, last updated timestamp
- **Quality Control**: Filter out advisory content, opinions, recommendations

---

## Phase 2: Vector Store & Indexing

### 2.1 Embedding Model Selection
- **Model**: BGE Large English v1.5 (bge-large-en-v1.5) - optimized for semantic search
- **Dimension**: 1024 dimensions for high-quality representations
- **Fine-tuning**: Optional fine-tuning on financial Q&A pairs

### 2.2 Vector Database Architecture
```
Documents → Embedding Generation → Vector Storage → Index Creation
```

**Storage Schema**:
```json
{
  "id": "unique_chunk_id",
  "content": "chunk_text",
  "embedding": [vector_array],
  "metadata": {
    "source_url": "original_url",
    "document_type": "factsheet|kim|sid|faq|performance_page",
    "last_updated": "timestamp",
    "amc": "Nippon India Mutual Funds",
    "scheme_name": "Large Cap Fund|Flexi Cap Fund|Multi Asset Allocation Fund",
    "source_category": "amc_official|groww aggregator|regulatory",
    "chunk_index": 1
  }
}
```

### 2.3 Indexing Strategy
- **Primary Index**: Cosine similarity search on embeddings
- **Secondary Indexes**: 
  - Metadata filters (AMC, scheme, document type, source_category)
  - Full-text search for exact matches
  - Temporal index for recency
  - Scheme-specific filters for targeted queries

---

## Phase 3: Query Processing & Retrieval

### 3.1 Query Understanding
```
User Query → Intent Classification → Query Expansion → Entity Extraction
```

**Components**:
- **Intent Classifier**: Distinguishes factual vs. advisory queries
- **Query Expander**: Adds relevant financial terminology
- **Entity Extractor**: Identifies fund names (Large Cap, Flexi Cap, Multi Asset Allocation), AMC (Nippon India), metrics (expense ratio, exit load, etc.)

### 3.2 Retrieval Pipeline
```
Query → Embedding → Vector Search → Metadata Filtering → Reranking
```

**Retrieval Strategy**:
- **Hybrid Search**: Combine semantic and keyword search
- **Candidate Generation**: Top 20 initial results
- **Reranking**: Relevance scoring based on:
  - Semantic similarity
  - Source authority (AMC official > Groww aggregator > Regulatory)
  - Content recency
  - Query term coverage
  - Document type priority (SID > Factsheet > Performance Page > FAQ)

### 3.3 Context Assembly
- **Top-k Selection**: Select 3-5 most relevant chunks
- **Context Window**: Ensure total context fits model limits
- **Source Attribution**: Maintain source links for each chunk

---

## Phase 4: Response Generation

### 4.1 Groq LLM Integration
```
System Prompt + Context + Query → Groq LLM → Structured Response
```

**Groq LLM Configuration**:
- **Model**: Groq LLaMA-3-8B-Instruct (llama-3-8b-instruct) - optimized for fast inference
- **Alternative Models**: Groq Mixtral-8x7B-Instruct, Groq Gemma-7B-Instruct
- **API Endpoint**: Groq Cloud API with ultra-low latency
- **Rate Limits**: 30 requests/minute (free tier), higher for paid plans

**System Prompt Components**:
- Role definition (facts-only assistant)
- Response constraints (max 3 sentences)
- Citation requirements
- Refusal handling guidelines
- Groq-specific optimization for speed

### 4.2 Response Structure
```json
{
  "answer": "factual_response",
  "source_url": "single_source_link",
  "last_updated": "date",
  "is_advisory": false,
  "confidence_score": 0.95
}
```

### 4.3 Groq Content Generation Rules
- **Length Limitation**: Maximum 3 sentences per response
- **Factual Accuracy**: Only use information from retrieved context
- **Source Citation**: Exactly one source URL per response
- **Compliance Check**: Automatic validation for advisory content
- **Groq Optimization**: Leverage Groq's hardware acceleration for speed
- **Token Efficiency**: Optimized prompts for faster processing

---

## Phase 5: Compliance & Safety Layer

### 5.1 Content Filtering
```
Response Generation → Advisory Detection → Compliance Check → Output
```

**Filter Categories**:
- Investment advice detection
- Performance comparisons
- Return calculations
- Personalized recommendations

### 5.2 Refusal Handling
- **Trigger Detection**: Identify advisory or non-factual queries
- **Response Templates**: Pre-approved refusal messages
- **Educational Links**: Provide AMFI/SEBI resources
- **Polite Declination**: Maintain helpful tone while refusing

### 5.3 Audit Trail
- **Query Logging**: Store all user queries (no PII)
- **Response Tracking**: Log generated responses and sources
- **Compliance Monitoring**: Regular review of response patterns

---

## Phase 6: Multi-thread Support & Session Management

### 6.1 Session Architecture
```
User → Session Manager → Thread Pool → RAG Pipeline → Response
```

**Components**:
- **Session Manager**: Handles multiple concurrent conversations
- **Thread Pool**: Isolates conversation contexts
- **State Management**: Maintains conversation history within threads
- **Resource Allocation**: Manages computational resources per thread

### 6.2 Context Management
- **Thread Isolation**: Separate context for each conversation
- **Memory Limits**: Prevent context overflow in long conversations
- **Session Persistence**: Optional conversation persistence
- **Load Balancing**: Distribute requests across available resources

---

## Phase 7: User Interface & Integration

### 7.1 Frontend Architecture
```
React/Vue.js → API Gateway → RAG Service → Response Display
```

**UI Components**:
- **Welcome Interface**: Clear disclaimer and example questions
- **Chat Interface**: Real-time conversation display
- **Source Display**: Prominent citation links
- **Error Handling**: Graceful failure messages

### 7.2 API Design
```
POST /api/chat
{
  "message": "user_query",
  "thread_id": "session_identifier",
  "context": "optional_previous_context"
}
```

**Response Format**:
```json
{
  "response": "answer_text",
  "source_url": "citation_link",
  "last_updated": "2024-01-15",
  "is_advisory": false,
  "thread_id": "conversation_id"
}
```

---

## Phase 8: Monitoring & Optimization

### 8.1 Performance Metrics
- **Response Latency**: Target < 2 seconds
- **Retrieval Accuracy**: Relevance scoring
- **User Satisfaction**: Feedback collection
- **System Uptime**: Availability monitoring

### 8.2 Data Quality Monitoring
- **Scraping Success Rate**: Monitor daily update completion
- **Source Availability**: Track URL accessibility and response times
- **Content Freshness**: Verify data recency and update frequency
- **Change Detection**: Alert on significant content modifications

### 8.3 Scheduler Health Monitoring
- **Job Execution**: Track daily 9:30 AM IST GitHub Actions workflow completion
- **Failure Analysis**: Monitor workflow step failures and retry attempts
- **Performance Trends**: Analyze workflow duration and runner performance
- **Resource Usage**: Monitor GitHub Actions runner utilization and timeouts
- **Workflow Status**: Track success/failure rates across different stages
- **Secret Rotation**: Monitor API key expiration and rotation schedules

### 8.4 Quality Assurance
- **Response Validation**: Automated fact-checking
- **Source Verification**: Link validity checks
- **Compliance Audits**: Regular content review
- **A/B Testing**: Prompt and model optimization

### 8.5 Continuous Improvement
- **User Feedback Integration**: Learn from corrections
- **Source Updates**: Regular content refresh via scheduler
- **Model Updates**: Periodic embedding model upgrades
- **Performance Tuning**: Optimize retrieval and generation
- **Scraping Optimization**: Improve extraction accuracy and speed

---

## Technology Stack

### Backend
- **Vector Database**: SQLite (with vector extensions), Pinecone, Weaviate, or Chroma
- **LLM**: BGE-based retrieval with template responses, or GPT-4/Claude for enhanced generation
- **Web Framework**: FastAPI or Flask
- **Task Queue**: Celery for background processing
- **Scheduler**: GitHub Actions for 9:30 AM IST automated workflows
- **Scraping Framework**: Scrapy with Selenium for dynamic content
- **PDF Processing**: PyPDF2, pdfplumber for document extraction
- **Message Queue**: Redis or RabbitMQ for job management
- **CI/CD**: GitHub Actions for automated data refresh and deployment

### Frontend
- **Framework**: React.js or Vue.js
- **Styling**: Tailwind CSS
- **State Management**: Redux or Context API
- **UI Components**: Material-UI or custom components

### Infrastructure
- **Deployment**: Docker containers
- **Scalability**: Kubernetes or serverless functions
- **Monitoring**: Prometheus + Grafana
- **Logging**: ELK stack or similar
- **Scheduling**: GitHub Actions workflows for automated data refresh
- **Storage**: AWS S3 or equivalent for scraped data backup
- **CDN**: CloudFlare for source URL access optimization
- **CI/CD**: GitHub Actions for continuous integration and deployment

---

## Security & Privacy Considerations

### Data Protection
- **No PII Collection**: Strict policy against personal data
- **Secure Storage**: Encrypted data at rest
- **Access Control**: Role-based permissions
- **Audit Logging**: Comprehensive access tracking

### Compliance
- **SEBI Guidelines**: Adherence to regulatory requirements
- **Data Privacy**: Compliance with data protection laws
- **Content Moderation**: Regular content reviews
- **Transparency**: Clear disclosure of limitations

---

## Implementation Timeline

### Phase 1-2 (Weeks 1-2): Foundation
- Data collection and processing pipeline
- Vector store setup and indexing

### Phase 3-4 (Weeks 3-4): Core RAG
- Query processing and retrieval
- Response generation and compliance

### Phase 5-6 (Weeks 5-6): Safety & Scaling
- Compliance layer implementation
- Multi-thread support

### Phase 7-8 (Weeks 7-8): Integration & Optimization
- UI development and integration
- Monitoring and optimization

---

## Success Metrics

### Technical Metrics
- **Accuracy**: >95% factual accuracy
- **Latency**: <2 second response time
- **Availability**: >99.5% uptime
- **Compliance**: 100% adherence to constraints

### User Metrics
- **Query Success Rate**: >90% successful responses
- **User Satisfaction**: >4.5/5 rating
- **Advisory Refusal Rate**: 100% for non-factual queries
- **Source Citation Accuracy**: 100% valid links

This architecture provides a robust, scalable, and compliant foundation for the mutual fund FAQ assistant, ensuring accurate, source-backed information while maintaining strict adherence to regulatory requirements.
