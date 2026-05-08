# Chunking and Embedding Architecture for Mutual Fund FAQ Assistant

## Overview
This document outlines the detailed architecture for text chunking and embedding generation processes that transform raw scraped data into searchable vector representations for the RAG system.

---

## Phase 1: Data Preprocessing Pipeline

### 1.1 Input Data Structure
```
Raw Scraped Data → Content Classification → Text Extraction → Structured Format
```

**Input Sources**:
- HTML content from web pages
- PDF documents (SIDs, KIMs)
- JSON data from API responses
- Structured tables and lists

**Data Schema**:
```json
{
  "source_url": "string",
  "document_type": "sid|factsheet|performance_page|faq",
  "scheme_name": "Large Cap Fund|Flexi Cap Fund|Multi Asset Allocation Fund",
  "amc": "Nippon India Mutual Funds",
  "raw_content": "string|binary",
  "content_type": "html|pdf|json|text",
  "extracted_at": "timestamp",
  "file_size": "bytes"
}
```

### 1.2 Content Extraction
```
Raw Content → Format Parser → Text Extraction → Structure Preservation
```

**Parsers by Type**:
- **HTML Parser**: BeautifulSoup4 with custom selectors
- **PDF Parser**: PyPDF2 + pdfplumber for complex layouts
- **Table Extractor**: pandas for tabular data
- **List Extractor**: Custom regex for bullet points and numbered lists

**Extraction Rules**:
- Preserve section headers (H1-H6 tags)
- Maintain table structure with column headers
- Extract list items with hierarchy
- Remove navigation, footers, and advertisements
- Preserve semantic meaning and relationships

---

## Phase 2: Intelligent Chunking Strategy

### 2.1 Semantic Chunking Approach
```
Document → Section Detection → Context Analysis → Chunk Generation → Quality Validation
```

**Chunking Principles**:
- **Semantic Coherence**: Keep related information together
- **Context Preservation**: Maintain surrounding context
- **Size Optimization**: 200-500 tokens per chunk
- **Overlap Strategy**: 50-100 token overlap for continuity

### 2.2 Chunking Algorithms

#### 2.2.1 Section-Based Chunking
```python
# Pseudocode for section-based chunking
def section_based_chunking(document):
    sections = extract_sections(document)
    chunks = []
    
    for section in sections:
        if section.token_count <= MAX_CHUNK_SIZE:
            chunks.append(create_chunk(section))
        else:
            # Further divide large sections
            sub_chunks = recursive_chunk(section)
            chunks.extend(sub_chunks)
    
    return add_overlap(chunks)
```

**Section Detection Rules**:
- HTML headings (H1-H6) as natural boundaries
- PDF document structure (chapters, sections)
- Table boundaries and list groupings
- Semantic paragraph breaks

#### 2.2.2 Sliding Window Chunking
```python
# Pseudocode for sliding window approach
def sliding_window_chunking(text, window_size=400, overlap=50):
    chunks = []
    tokens = tokenize(text)
    
    for i in range(0, len(tokens), window_size - overlap):
        window = tokens[i:i + window_size]
        chunk = detokenize(window)
        chunks.append(chunk)
    
    return chunks
```

#### 2.2.3 Hybrid Chunking Strategy
```python
# Combines semantic and sliding window approaches
def hybrid_chunking(document):
    # First try semantic chunking
    semantic_chunks = section_based_chunking(document)
    
    # Handle oversized chunks with sliding window
    final_chunks = []
    for chunk in semantic_chunks:
        if chunk.token_count > MAX_CHUNK_SIZE:
            sub_chunks = sliding_window_chunking(chunk.content)
            final_chunks.extend(sub_chunks)
        else:
            final_chunks.append(chunk)
    
    return final_chunks
```

### 2.3 Chunk Metadata Enrichment
```json
{
  "chunk_id": "unique_identifier",
  "content": "chunk_text_content",
  "token_count": 350,
  "chunk_type": "section|paragraph|table|list",
  "position": {
    "document_index": 1,
    "section_index": 3,
    "paragraph_index": 5
  },
  "context": {
    "preceding_chunk": "prev_chunk_id",
    "following_chunk": "next_chunk_id",
    "section_title": "Expense Ratio Details",
    "parent_section": "Fund Information"
  },
  "source_metadata": {
    "source_url": "original_url",
    "document_type": "sid",
    "scheme_name": "Large Cap Fund",
    "extraction_date": "timestamp"
  }
}
```

---

## Phase 3: Embedding Generation Pipeline

### 3.1 Embedding Model Selection
```
Model Selection → Tokenization → Embedding Generation → Vector Normalization → Storage
```

**Model Options**:
- **Primary**: BGE Large English v1.5 (bge-large-en-v1.5) - 1024 dimensions
- **Alternative**: Sentence-BERT (all-MiniLM-L6-v2) - 384 dimensions
- **Domain-Specific**: Fine-tuned BGE on financial Q&A data

**Selection Criteria**:
- **Performance**: >90% semantic similarity on financial queries
- **Efficiency**: <100ms per embedding generation
- **Size**: <500MB model size for deployment
- **Compatibility**: Support for batch processing

### 3.2 Text Preprocessing for Embedding
```python
def preprocess_for_embedding(text):
    # Clean and normalize text
    text = remove_special_characters(text)
    text = normalize_whitespace(text)
    text = expand_financial_abbreviations(text)
    
    # Tokenize based on model requirements
    tokens = model_tokenizer(text, 
                           max_length=MAX_TOKENS,
                           truncation=True,
                           padding=True)
    
    return tokens
```

**Preprocessing Steps**:
- **Financial Abbreviation Expansion**: 
  - "ELSS" → "Equity Linked Savings Scheme"
  - "SIP" → "Systematic Investment Plan"
  - "NAV" → "Net Asset Value"
- **Number Normalization**: Standardize date formats, percentages
- **Entity Recognition**: Preserve fund names, AMC names
- **Noise Removal**: Eliminate HTML artifacts, formatting characters

### 3.3 Batch Embedding Generation
```python
class EmbeddingGenerator:
    def __init__(self, model_name, batch_size=32):
        self.model = load_model(model_name)
        self.batch_size = batch_size
        
    def generate_embeddings(self, chunks):
        embeddings = []
        
        for i in range(0, len(chunks), self.batch_size):
            batch = chunks[i:i + self.batch_size]
            batch_embeddings = self.model.encode(
                [chunk.content for chunk in batch],
                batch_size=self.batch_size,
                show_progress_bar=True
            )
            embeddings.extend(batch_embeddings)
        
        return embeddings
```

**Batch Processing Features**:
- **Memory Optimization**: Process chunks in configurable batches
- **Progress Tracking**: Real-time progress monitoring
- **Error Handling**: Retry failed embeddings individually
- **Caching**: Cache embeddings for unchanged content

---

## Phase 4: Vector Storage and Indexing

### 4.1 Vector Database Schema
```json
{
  "vectors": {
    "id": "chunk_id",
    "values": [0.1, 0.2, 0.3, ...],
    "metadata": {
      "content": "chunk_text",
      "source_url": "original_url",
      "document_type": "sid|factsheet|performance",
      "scheme_name": "fund_name",
      "chunk_type": "section|table|list",
      "token_count": 350,
      "created_at": "timestamp",
      "last_updated": "timestamp"
    }
  }
}
```

### 4.2 Indexing Strategy
```
Vectors → HNSW Index → Metadata Index → Hybrid Search Index
```

**Index Types**:
- **HNSW Index**: Hierarchical Navigable Small World for approximate nearest neighbor
- **Metadata Index**: Filter by source, document type, scheme
- **Full-text Index**: Exact keyword matching
- **Temporal Index**: Sort by recency

### 4.3 Similarity Search Configuration
```python
search_config = {
    "vector_search": {
        "metric": "cosine",
        "top_k": 20,
        "threshold": 0.7
    },
    "hybrid_search": {
        "alpha": 0.7,  # weight for vector search
        "beta": 0.3    # weight for keyword search
    },
    "filters": {
        "document_type": ["sid", "factsheet"],
        "scheme_name": "Large Cap Fund",
        "source_category": "amc_official"
    }
}
```

---

## Phase 5: Quality Assurance and Validation

### 5.1 Chunk Quality Metrics
```python
def validate_chunk_quality(chunk):
    metrics = {
        "length_score": calculate_length_score(chunk),
        "coherence_score": calculate_coherence(chunk),
        "completeness_score": calculate_completeness(chunk),
        "relevance_score": calculate_relevance(chunk)
    }
    
    overall_score = weighted_average(metrics)
    return overall_score > QUALITY_THRESHOLD
```

**Quality Checks**:
- **Length Validation**: 200-500 tokens optimal
- **Semantic Coherence**: Maintains context and meaning
- **Completeness**: Contains complete information units
- **Relevance**: Contains factual mutual fund information

### 5.2 Embedding Quality Validation
```python
def validate_embedding_quality(embedding, reference_embeddings):
    # Compare with similar known embeddings
    similarity_scores = cosine_similarity(embedding, reference_embeddings)
    
    # Check for embedding drift
    drift_score = calculate_drift(embedding, historical_embeddings)
    
    # Validate vector properties
    norm_score = np.linalg.norm(embedding)
    
    return {
        "similarity_score": np.mean(similarity_scores),
        "drift_score": drift_score,
        "norm_score": norm_score
    }
```

---

## Phase 6: Performance Optimization

### 6.1 Caching Strategy
```
Content Hash → Cache Check → Embedding Retrieval → New Generation → Cache Store
```

**Cache Layers**:
- **Content Hash Cache**: Cache embeddings by content hash
- **Vector Cache**: In-memory cache for frequently accessed vectors
- **Metadata Cache**: Cache chunk metadata for quick filtering

### 6.2 Parallel Processing
```python
def parallel_chunking(documents, num_workers=4):
    with ProcessPoolExecutor(max_workers=num_workers) as executor:
        futures = [executor.submit(chunk_document, doc) 
                  for doc in documents]
        
        results = []
        for future in as_completed(futures):
            chunks = future.result()
            results.extend(chunks)
    
    return results
```

**Optimization Features**:
- **Multi-processing**: Parallel chunking and embedding
- **GPU Acceleration**: CUDA support for embedding generation
- **Memory Management**: Efficient memory usage for large documents
- **Batch Optimization**: Dynamic batch sizing based on content

---

## Phase 7: Monitoring and Maintenance

### 7.1 Performance Metrics
- **Chunking Speed**: Documents processed per minute
- **Embedding Generation**: Embeddings per second
- **Storage Efficiency**: Compression ratio and storage usage
- **Search Performance**: Query response time

### 7.2 Quality Monitoring
- **Embedding Drift**: Monitor changes in embedding distributions
- **Chunk Quality**: Track quality scores over time
- **Search Relevance**: Measure search result accuracy
- **User Feedback**: Collect feedback on response quality

### 7.3 Maintenance Tasks
- **Index Rebuilding**: Periodic index optimization
- **Cache Cleanup**: Remove outdated cache entries
- **Model Updates**: Update embedding models periodically
- **Storage Optimization**: Compress and archive old data

---

## Technology Stack

### Core Libraries
- **Text Processing**: NLTK, spaCy, BeautifulSoup4
- **PDF Processing**: PyPDF2, pdfplumber
- **Embedding Models**: sentence-transformers, transformers
- **Vector Databases**: Pinecone, Weaviate, Chroma
- **Caching**: Redis, Memcached

### ML/AI Frameworks
- **PyTorch**: For custom embedding models
- **Hugging Face**: Pre-trained transformer models
- **Scikit-learn**: Similarity calculations and metrics
- **NumPy/Pandas**: Data processing and analysis

### Deployment
- **Docker**: Containerized processing services
- **Kubernetes**: Orchestration for scaling
- **AWS/GCP**: Cloud infrastructure
- **Monitoring**: Prometheus, Grafana

---

## Configuration Examples

### Chunking Configuration
```yaml
chunking:
  max_chunk_size: 500
  min_chunk_size: 200
  overlap_size: 50
  chunking_strategy: "hybrid"
  preserve_structure: true
  section_headers: ["h1", "h2", "h3", "h4", "h5", "h6"]
```

### Embedding Configuration
```yaml
embedding:
  model_name: "BAAI/bge-large-en-v1.5"
  batch_size: 32
  max_length: 512
  normalize_embeddings: true
  use_gpu: true
  cache_embeddings: true
```

### Vector Store Configuration
```yaml
vector_store:
  type: "sqlite"  # Options: sqlite, chromadb, pinecone, weaviate
  index_name: "mutual-fund-faq"
  dimension: 1024
  metric: "cosine"
  database_path: "./data/vector_store.db"
  vector_extension: "sqlite-vss"  # SQLite Vector Search Extension
```

### LLM Configuration (Groq)
```yaml
llm:
  type: "groq"
  model: "llama-3-8b-instruct"  # Groq LLaMA-3-8B-Instruct
  api_key: "${GROQ_API_KEY}"
  temperature: 0.1
  max_tokens: 200
  timeout: 30
  rate_limit: 30  # requests per minute
```

This architecture provides a comprehensive framework for transforming raw mutual fund data into high-quality, searchable vector representations that power accurate and efficient RAG-based question answering with ultra-fast Groq LLM inference.
