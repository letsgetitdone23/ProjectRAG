"""
Vector Storage and Indexing System for Mutual Fund FAQ Assistant
Implements vector database operations with Pinecone/Weaviate support
"""

import logging
import json
import numpy as np
from typing import List, Dict, Optional, Tuple, Any
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
import hashlib

# Try to import vector database clients
try:
    import pinecone
    PINECONE_AVAILABLE = True
except ImportError:
    PINECONE_AVAILABLE = False

# Import SQLite vector store
try:
    from .sqlite_simple import SimpleSQLiteVectorStore as SQLiteVectorStore
    SQLITE_AVAILABLE = True
except ImportError:
    SQLITE_AVAILABLE = False
    # Create a fallback class if import fails
    class SQLiteVectorStore:
        def __init__(self, *args, **kwargs):
            raise ImportError("SQLite vector store not available")

try:
    import weaviate
    WEAVIATE_AVAILABLE = True
except ImportError:
    WEAVIATE_AVAILABLE = False

try:
    import chromadb
    CHROMADB_AVAILABLE = True
except ImportError:
    CHROMADB_AVAILABLE = False

@dataclass
class VectorRecord:
    """Represents a vector record with metadata"""
    id: str
    vector: List[float]
    content: str
    metadata: Dict
    source_url: str
    document_type: str
    scheme_name: str
    chunk_type: str
    token_count: int
    created_at: str
    last_updated: str

class VectorStore:
    """Abstract base class for vector storage implementations"""
    
    def __init__(self, config: Dict):
        self.config = config
        self.logger = logging.getLogger(__name__)
        self.index_name = config.get('index_name', 'mutual-fund-faq')
        self.dimension = config.get('dimension', 384)
        self.metric = config.get('metric', 'cosine')
    
    def add_vectors(self, vectors: List[VectorRecord]) -> bool:
        """Add vectors to the store"""
        raise NotImplementedError
    
    def search(self, query_vector: List[float], top_k: int = 10, 
               filters: Optional[Dict] = None) -> List[Dict]:
        """Search for similar vectors"""
        raise NotImplementedError
    
    def delete_vectors(self, ids: List[str]) -> bool:
        """Delete vectors by ID"""
        raise NotImplementedError
    
    def get_stats(self) -> Dict:
        """Get storage statistics"""
        raise NotImplementedError

class PineconeVectorStore(VectorStore):
    """Pinecone implementation of vector storage"""
    
    def __init__(self, config: Dict):
        super().__init__(config)
        
        if not PINECONE_AVAILABLE:
            raise ImportError("Pinecone client not available. Install with: pip install pinecone-client")
        
        # Initialize Pinecone
        api_key = config.get('api_key')
        environment = config.get('environment')
        
        if not api_key:
            raise ValueError("Pinecone API key is required")
        
        pinecone.init(api_key=api_key, environment=environment)
        self.client = pinecone
        
        # Create or connect to index
        self._ensure_index_exists()
        self.index = self.client.Index(self.index_name)
    
    def _ensure_index_exists(self):
        """Ensure the index exists"""
        if self.index_name not in self.client.list_indexes():
            self.logger.info(f"Creating new index: {self.index_name}")
            self.client.create_index(
                name=self.index_name,
                dimension=self.dimension,
                metric=self.metric
            )
        else:
            self.logger.info(f"Using existing index: {self.index_name}")
    
    def add_vectors(self, vectors: List[VectorRecord]) -> bool:
        """Add vectors to Pinecone"""
        try:
            # Prepare batch data
            batch_data = []
            for record in vectors:
                batch_data.append({
                    'id': record.id,
                    'values': record.vector,
                    'metadata': {
                        'content': record.content,
                        'source_url': record.source_url,
                        'document_type': record.document_type,
                        'scheme_name': record.scheme_name,
                        'chunk_type': record.chunk_type,
                        'token_count': record.token_count,
                        'created_at': record.created_at,
                        'last_updated': record.last_updated,
                        **record.metadata
                    }
                })
            
            # Upsert in batches
            batch_size = 100
            for i in range(0, len(batch_data), batch_size):
                batch = batch_data[i:i + batch_size]
                self.index.upsert(vectors=batch)
            
            self.logger.info(f"Added {len(vectors)} vectors to Pinecone")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to add vectors to Pinecone: {str(e)}")
            return False
    
    def search(self, query_vector: List[float], top_k: int = 10, 
               filters: Optional[Dict] = None) -> List[Dict]:
        """Search in Pinecone"""
        try:
            # Prepare query parameters
            query_params = {
                'vector': query_vector,
                'top_k': top_k,
                'include_metadata': True
            }
            
            # Add filters if provided
            if filters:
                query_params['filter'] = filters
            
            # Execute search
            results = self.index.query(**query_params)
            
            # Format results
            formatted_results = []
            for match in results['matches']:
                formatted_results.append({
                    'id': match['id'],
                    'score': match['score'],
                    'content': match['metadata'].get('content', ''),
                    'source_url': match['metadata'].get('source_url', ''),
                    'document_type': match['metadata'].get('document_type', ''),
                    'scheme_name': match['metadata'].get('scheme_name', ''),
                    'chunk_type': match['metadata'].get('chunk_type', ''),
                    'metadata': match['metadata']
                })
            
            return formatted_results
            
        except Exception as e:
            self.logger.error(f"Failed to search in Pinecone: {str(e)}")
            return []
    
    def delete_vectors(self, ids: List[str]) -> bool:
        """Delete vectors from Pinecone"""
        try:
            self.index.delete(ids=ids)
            self.logger.info(f"Deleted {len(ids)} vectors from Pinecone")
            return True
        except Exception as e:
            self.logger.error(f"Failed to delete vectors from Pinecone: {str(e)}")
            return False
    
    def get_stats(self) -> Dict:
        """Get Pinecone statistics"""
        try:
            stats = self.index.describe_index_stats()
            return {
                'total_vectors': stats.get('total_vector_count', 0),
                'dimension': stats.get('dimension', self.dimension),
                'index_fullness': stats.get('index_fullness', 0.0),
                'namespace_count': len(stats.get('namespaces', {}))
            }
        except Exception as e:
            self.logger.error(f"Failed to get Pinecone stats: {str(e)}")
            return {}

class ChromaDBVectorStore(VectorStore):
    """ChromaDB implementation of vector store"""
    
    def __init__(self, index_name: str, dimension: int = 1024, metric: str = "cosine",
                 persist_directory: str = "./chroma_db"):
        self.index_name = index_name
        self.dimension = dimension
        self.metric = metric
        self.persist_directory = persist_directory
        
        if not CHROMADB_AVAILABLE:
            raise ImportError("ChromaDB client not available. Install with: pip install chromadb")
        
        # Initialize ChromaDB
        self.client = chromadb.ChromaDB(persist_directory=self.persist_directory)
        
        # Create or connect to index
        self._ensure_index_exists()
    
    def _ensure_index_exists(self):
        """Ensure the index exists"""
        if self.index_name not in self.client.list_indexes():
            self.logger.info(f"Creating new index: {self.index_name}")
            self.client.create_index(
                name=self.index_name,
                dimension=self.dimension,
                metric=self.metric
            )
        else:
            self.logger.info(f"Using existing index: {self.index_name}")
    
    def add_vectors(self, vectors: List[VectorRecord]) -> bool:
        """Add vectors to ChromaDB"""
        try:
            # Prepare batch data
            batch_data = []
            for record in vectors:
                batch_data.append({
                    'id': record.id,
                    'vector': record.vector,
                    'metadata': {
                        'content': record.content,
                        'source_url': record.source_url,
                        'document_type': record.document_type,
                        'scheme_name': record.scheme_name,
                        'chunk_type': record.chunk_type,
                        'token_count': record.token_count,
                        'created_at': record.created_at,
                        'last_updated': record.last_updated,
                        **record.metadata
                    }
                })
            
            # Upsert in batches
            batch_size = 100
            for i in range(0, len(batch_data), batch_size):
                batch = batch_data[i:i + batch_size]
                self.client.add(batch)
            
            self.logger.info(f"Added {len(vectors)} vectors to ChromaDB")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to add vectors to ChromaDB: {str(e)}")
            return False
    
    def search(self, query_vector: List[float], top_k: int = 10, 
               filters: Optional[Dict] = None) -> List[Dict]:
        """Search in ChromaDB"""
        try:
            # Prepare query parameters
            query_params = {
                'vector': query_vector,
                'top_k': top_k
            }
            
            # Add filters if provided
            if filters:
                query_params['filter'] = filters
            
            # Execute search
            results = self.client.search(**query_params)
            
            # Format results
            formatted_results = []
            for match in results:
                formatted_results.append({
                    'id': match['id'],
                    'score': match['score'],
                    'content': match['metadata'].get('content', ''),
                    'source_url': match['metadata'].get('source_url', ''),
                    'document_type': match['metadata'].get('document_type', ''),
                    'scheme_name': match['metadata'].get('scheme_name', ''),
                    'chunk_type': match['metadata'].get('chunk_type', ''),
                    'metadata': match['metadata']
                })
            
            return formatted_results
            
        except Exception as e:
            self.logger.error(f"Failed to search in ChromaDB: {str(e)}")
            return []
    
    def delete_vectors(self, ids: List[str]) -> bool:
        """Delete vectors from ChromaDB"""
        try:
            self.client.delete(ids=ids)
            self.logger.info(f"Deleted {len(ids)} vectors from ChromaDB")
            return True
        except Exception as e:
            self.logger.error(f"Failed to delete vectors from ChromaDB: {str(e)}")
            return False
    
    def get_stats(self) -> Dict:
        """Get ChromaDB statistics"""
        try:
            stats = self.client.describe_index_stats()
            return {
                'total_vectors': stats.get('total_vector_count', 0),
                'dimension': stats.get('dimension', self.dimension),
                'index_fullness': stats.get('index_fullness', 0.0),
                'namespace_count': len(stats.get('namespaces', {}))
            }
        except Exception as e:
            self.logger.error(f"Failed to get ChromaDB stats: {str(e)}")
            return {}

class WeaviateVectorStore(VectorStore):
    """Weaviate implementation of vector storage"""
    
    def __init__(self, config: Dict):
        super().__init__(config)
        
        if not WEAVIATE_AVAILABLE:
            raise ImportError("Weaviate client not available. Install with: pip install weaviate-client")
        
        # Initialize Weaviate
        url = config.get('url')
        api_key = config.get('api_key')
        
        if not url:
            raise ValueError("Weaviate URL is required")
        
        auth_config = None
        if api_key:
            auth_config = weaviate.AuthApiKey(api_key)
        
        self.client = weaviate.Client(url=url, auth_client=auth_config)
        
        # Ensure schema exists
        self._ensure_schema_exists()
    
    def _ensure_schema_exists(self):
        """Ensure the schema exists"""
        class_name = "MutualFundChunk"
        
        # Check if class exists
        existing_classes = [cls['class'] for cls in self.client.schema.get()['classes']]
        
        if class_name not in existing_classes:
            # Create schema
            schema = {
                "class": class_name,
                "description": "Mutual fund FAQ chunks",
                "vectorizer": "none",  # We provide our own vectors
                "properties": [
                    {
                        "name": "content",
                        "dataType": ["text"],
                        "description": "Chunk content"
                    },
                    {
                        "name": "sourceUrl",
                        "dataType": ["string"],
                        "description": "Source URL"
                    },
                    {
                        "name": "documentType",
                        "dataType": ["string"],
                        "description": "Document type"
                    },
                    {
                        "name": "schemeName",
                        "dataType": ["string"],
                        "description": "Scheme name"
                    },
                    {
                        "name": "chunkType",
                        "dataType": ["string"],
                        "description": "Chunk type"
                    },
                    {
                        "name": "tokenCount",
                        "dataType": ["int"],
                        "description": "Token count"
                    },
                    {
                        "name": "createdAt",
                        "dataType": ["string"],
                        "description": "Creation timestamp"
                    },
                    {
                        "name": "lastUpdated",
                        "dataType": ["string"],
                        "description": "Last update timestamp"
                    }
                ]
            }
            
            self.client.schema.create_class(schema)
            self.logger.info(f"Created Weaviate class: {class_name}")
    
    def add_vectors(self, vectors: List[VectorRecord]) -> bool:
        """Add vectors to Weaviate"""
        try:
            class_name = "MutualFundChunk"
            
            # Prepare batch data
            with self.client.batch as batch:
                batch.batch_size = 100
                
                for record in vectors:
                    properties = {
                        'content': record.content,
                        'sourceUrl': record.source_url,
                        'documentType': record.document_type,
                        'schemeName': record.scheme_name,
                        'chunkType': record.chunk_type,
                        'tokenCount': record.token_count,
                        'createdAt': record.created_at,
                        'lastUpdated': record.last_updated
                    }
                    
                    # Add additional metadata
                    for key, value in record.metadata.items():
                        if key not in properties:
                            properties[key] = value
                    
                    batch.add_data_object(
                        properties=properties,
                        class_name=class_name,
                        vector=record.vector
                    )
            
            self.logger.info(f"Added {len(vectors)} vectors to Weaviate")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to add vectors to Weaviate: {str(e)}")
            return False
    
    def search(self, query_vector: List[float], top_k: int = 10, 
               filters: Optional[Dict] = None) -> List[Dict]:
        """Search in Weaviate"""
        try:
            class_name = "MutualFundChunk"
            
            # Build query
            near_vector = {"vector": query_vector}
            
            # Add filters if provided
            where_filter = None
            if filters:
                where_filter = self._build_weaviate_filter(filters)
            
            # Execute search
            results = self.client.query.get(
                class_name, 
                ["content", "sourceUrl", "documentType", "schemeName", "chunkType", "tokenCount", "createdAt", "lastUpdated"]
            ).with_near_vector(near_vector).with_limit(top_k)
            
            if where_filter:
                results = results.with_where(where_filter)
            
            results = results.with_additional(['vector', 'id', 'certainty', 'distance']).do()
            
            # Format results
            formatted_results = []
            for result in results.get('data', {}).get('Get', {}).get(class_name, []):
                formatted_results.append({
                    'id': result.get('_id', ''),
                    'score': result.get('_certainty', 0.0),
                    'content': result.get('content', ''),
                    'source_url': result.get('sourceUrl', ''),
                    'document_type': result.get('documentType', ''),
                    'scheme_name': result.get('schemeName', ''),
                    'chunk_type': result.get('chunkType', ''),
                    'metadata': result
                })
            
            return formatted_results
            
        except Exception as e:
            self.logger.error(f"Failed to search in Weaviate: {str(e)}")
            return []
    
    def _build_weaviate_filter(self, filters: Dict) -> Dict:
        """Build Weaviate filter from dict"""
        conditions = []
        
        for key, value in filters.items():
            if isinstance(value, str):
                conditions.append({
                    "path": [key],
                    "operator": "Equal",
                    "valueString": value
                })
            elif isinstance(value, (list, tuple)):
                conditions.append({
                    "path": [key],
                    "operator": "ContainsAny",
                    "valueStringList": value
                })
        
        if len(conditions) == 1:
            return conditions[0]
        elif len(conditions) > 1:
            return {"operator": "And", "operands": conditions}
        else:
            return {}
    
    def delete_vectors(self, ids: List[str]) -> bool:
        """Delete vectors from Weaviate"""
        try:
            class_name = "MutualFundChunk"
            
            # Delete by ID
            for id in ids:
                self.client.data_object.delete(
                    class_name=class_name,
                    id=id
                )
            
            self.logger.info(f"Deleted {len(ids)} vectors from Weaviate")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to delete vectors from Weaviate: {str(e)}")
            return False
    
    def get_stats(self) -> Dict:
        """Get Weaviate statistics"""
        try:
            # Get schema info
            schema = self.client.schema.get()
            
            # Get class info
            class_name = "MutualFundChunk"
            class_info = None
            
            for cls in schema.get('classes', []):
                if cls['class'] == class_name:
                    class_info = cls
                    break
            
            return {
                'total_vectors': class_info.get('vectorIndexType', 'unknown'),
                'dimension': self.dimension,
                'class_name': class_name,
                'schema_version': schema.get('version', 'unknown')
            }
            
        except Exception as e:
            self.logger.error(f"Failed to get Weaviate stats: {str(e)}")
            return {}

class ChromaDBVectorStore(VectorStore):
    """ChromaDB implementation of vector storage (local/development)"""
    
    def __init__(self, config: Dict):
        super().__init__(config)
        
        if not CHROMADB_AVAILABLE:
            raise ImportError("ChromaDB client not available. Install with: pip install chromadb")
        
        # Initialize ChromaDB
        persist_directory = config.get('persist_directory', './chroma_db')
        self.client = chromadb.PersistentClient(path=persist_directory)
        
        # Get or create collection
        self.collection = self.client.get_or_create_collection(
            name=self.index_name,
            metadata={"hnsw:space": "cosine"}
        )
    
    def add_vectors(self, vectors: List[VectorRecord]) -> bool:
        """Add vectors to ChromaDB"""
        try:
            # Prepare data
            ids = [record.id for record in vectors]
            embeddings = [record.vector for record in vectors]
            documents = [record.content for record in vectors]
            metadatas = []
            
            # Remove duplicates by ID
            unique_vectors = {}
            for v in vectors:
                if v.id not in unique_vectors:
                    unique_vectors[v.id] = v
            
            vectors = list(unique_vectors.values())
            
            # Prepare data for ChromaDB
            ids = [v.id for v in vectors]
            embeddings = [v.vector for v in vectors]
            documents = [v.content for v in vectors]
            metadatas = [v.metadata for v in vectors]
            
            # Check if collection exists and has data
            try:
                existing_count = self.collection.count()
                if existing_count > 0:
                    # Delete existing documents with same IDs to avoid duplicates
                    self.collection.delete(ids=ids)
            except:
                pass
            
            # Add to collection
            self.collection.add(
                ids=ids,
                embeddings=embeddings,
                documents=documents,
                metadatas=metadatas
            )
            
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to add vectors to ChromaDB: {str(e)}")
            return False
    
    def search(self, query_vector: List[float], top_k: int = 10, 
               filters: Optional[Dict] = None) -> List[Dict]:
        """Search in ChromaDB"""
        try:
            # Prepare query parameters
            query_params = {
                'query_embeddings': [query_vector],
                'n_results': top_k,
                'include': ['metadatas', 'documents', 'distances']
            }
            
            # Add filters if provided
            if filters:
                query_params['where'] = filters
            
            # Execute search
            results = self.collection.query(**query_params)
            
            # Format results
            formatted_results = []
            
            if results['ids'] and results['ids'][0]:
                for i in range(len(results['ids'][0])):
                    formatted_results.append({
                        'id': results['ids'][0][i],
                        'score': 1.0 - results['distances'][0][i],  # Convert distance to similarity
                        'content': results['documents'][0][i],
                        'source_url': results['metadatas'][0][i].get('source_url', ''),
                        'document_type': results['metadatas'][0][i].get('document_type', ''),
                        'scheme_name': results['metadatas'][0][i].get('scheme_name', ''),
                        'chunk_type': results['metadatas'][0][i].get('chunk_type', ''),
                        'metadata': results['metadatas'][0][i]
                    })
            
            return formatted_results
            
        except Exception as e:
            self.logger.error(f"Failed to search in ChromaDB: {str(e)}")
            return []
    
    def delete_vectors(self, ids: List[str]) -> bool:
        """Delete vectors from ChromaDB"""
        try:
            self.collection.delete(ids=ids)
            self.logger.info(f"Deleted {len(ids)} vectors from ChromaDB")
            return True
        except Exception as e:
            self.logger.error(f"Failed to delete vectors from ChromaDB: {str(e)}")
            return False
    
    def get_stats(self) -> Dict:
        """Get ChromaDB statistics"""
        try:
            count = self.collection.count()
            return {
                'total_vectors': count,
                'dimension': self.dimension,
                'collection_name': self.index_name,
                'persist_directory': self.client._persist_directory
            }
        except Exception as e:
            self.logger.error(f"Failed to get ChromaDB stats: {str(e)}")
            return {}

class VectorStoreFactory:
    """Factory to create appropriate vector store"""
    
    @staticmethod
    def create_store(config: Dict) -> VectorStore:
        """Factory function to create vector store instance"""
        store_type = config.get('type', 'sqlite')
        store_type_lower = store_type.lower()
        
        if store_type_lower == 'sqlite' and SQLITE_AVAILABLE:
            return SQLiteVectorStore(config)
        elif store_type == 'pinecone':
            return PineconeVectorStore(config)
        elif store_type == 'weaviate':
            return WeaviateVectorStore(config)
        elif store_type == 'chromadb':
            return ChromaDBVectorStore(config)
        else:
            raise ValueError(f"Unsupported vector store type: {store_type}")

class VectorStoreManager:
    """Manager for vector store operations"""
    
    def __init__(self, config: Dict):
        self.config = config
        self.logger = logging.getLogger(__name__)
        self.vector_store = VectorStoreFactory.create_store(config)
    
    def store_embeddings(self, embeddings_data: List[Dict], chunks_data: List[Dict]) -> bool:
        """Store embeddings with chunk data"""
        try:
            # Create mapping from chunk ID to chunk data
            chunk_map = {chunk['id']: chunk for chunk in chunks_data}
            
            # Create vector records
            vector_records = []
            
            for embedding_data in embeddings_data:
                chunk_id = embedding_data['chunk_id']
                chunk_data = chunk_map.get(chunk_id)
                
                if not chunk_data:
                    self.logger.warning(f"No chunk data found for embedding: {chunk_id}")
                    continue
                
                record = VectorRecord(
                    id=chunk_id,
                    vector=embedding_data['embedding'],
                    content=chunk_data['content'],
                    metadata=chunk_data.get('source_metadata', {}),
                    source_url=chunk_data.get('source_metadata', {}).get('url', ''),
                    document_type=chunk_data.get('source_metadata', {}).get('document_type', ''),
                    scheme_name=chunk_data.get('source_metadata', {}).get('scheme_name', ''),
                    chunk_type=chunk_data['chunk_type'],
                    token_count=chunk_data['token_count'],
                    created_at=embedding_data['generation_timestamp'],
                    last_updated=embedding_data['generation_timestamp']
                )
                
                vector_records.append(record)
            
            # Store vectors
            success = self.vector_store.add_vectors(vector_records)
            
            if success:
                self.logger.info(f"Successfully stored {len(vector_records)} vectors")
            else:
                self.logger.error("Failed to store vectors")
            
            return success
            
        except Exception as e:
            self.logger.error(f"Error storing embeddings: {str(e)}")
            return False
    
    def search_similar(self, query_vector: List[float], top_k: int = 10, 
                      filters: Optional[Dict] = None) -> List[Dict]:
        """Search for similar content"""
        return self.vector_store.search(query_vector, top_k, filters)
    
    def get_store_stats(self) -> Dict:
        """Get vector store statistics"""
        return self.vector_store.get_stats()
