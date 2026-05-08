"""
Embedding Generation System using Sentence-BERT for Mutual Fund FAQ Assistant
"""

import logging
import json
import hashlib
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
import numpy as np
from sentence_transformers import SentenceTransformer
import torch
from tqdm import tqdm

@dataclass
class EmbeddingResult:
    """Result of embedding generation"""
    chunk_id: str
    embedding: List[float]
    embedding_dimension: int
    model_name: str
    generation_timestamp: str
    processing_time_ms: float
    cache_hit: bool = False

class EmbeddingGenerator:
    """Generates embeddings using Sentence-BERT model"""
    
    def __init__(self, model_name: str = "BAAI/bge-large-en-v1.5", 
                 batch_size: int = 32, max_length: int = 512,
                 use_gpu: bool = False, cache_embeddings: bool = True):
        self.model_name = model_name
        self.batch_size = batch_size
        self.max_length = max_length
        self.use_gpu = use_gpu
        self.enable_caching = cache_embeddings
        self.embedding_cache = {}
        self.logger = logging.getLogger(__name__)
        
        # Initialize model
        self.device = torch.device("cuda" if use_gpu and torch.cuda.is_available() else "cpu")
        self.model = SentenceTransformer(model_name)
        self.model.to(self.device)
    
    def _get_device(self) -> str:
        """Determine the best device for model inference"""
        if torch.cuda.is_available():
            return 'cuda'
        elif torch.backends.mps.is_available():
            return 'mps'
        else:
            return 'cpu'
    
    def _load_model(self):
        """Load the sentence transformer model"""
        try:
            self.logger.info(f"Loading embedding model: {self.model_name}")
            self.model = SentenceTransformer(self.model_name, device=self.device)
            
            # Test the model
            test_embedding = self.model.encode(["test"])
            self.embedding_dimension = len(test_embedding[0])
            
            self.logger.info(f"Model loaded successfully. Embedding dimension: {self.embedding_dimension}")
            self.logger.info(f"Using device: {self.device}")
            
        except Exception as e:
            self.logger.error(f"Failed to load model: {str(e)}")
            raise
    
    def generate_embeddings(self, chunks: List[Dict]) -> List[EmbeddingResult]:
        """Generate embeddings for a list of chunks"""
        if not chunks:
            return []
        
        self.logger.info(f"Generating embeddings for {len(chunks)} chunks")
        
        # Extract chunk contents and IDs
        chunk_contents = []
        chunk_ids = []
        
        for chunk in chunks:
            chunk_id = chunk['id']
            content = chunk['content']
            
            # Check cache first
            if self.enable_caching:
                content_hash = self._get_content_hash(content)
                if content_hash in self.embedding_cache:
                    cached_embedding = self.embedding_cache[content_hash]
                    result = EmbeddingResult(
                        chunk_id=chunk_id,
                        embedding=cached_embedding,
                        embedding_dimension=len(cached_embedding),
                        model_name=self.model_name,
                        generation_timestamp=datetime.now().isoformat(),
                        processing_time_ms=0.0,
                        cache_hit=True
                    )
                    # We'll add these later, continue with uncached ones
                    continue
            
            chunk_contents.append(content)
            chunk_ids.append(chunk_id)
        
        # Generate embeddings in batches
        results = []
        if chunk_contents:
            batch_results = self._generate_batch_embeddings(chunk_contents, chunk_ids)
            results.extend(batch_results)
        
        # Add cached results if any
        if self.enable_caching:
            cached_results = self._get_cached_results(chunks)
            results.extend(cached_results)
        
        self.logger.info(f"Generated {len(results)} embeddings")
        return results
    
    def _generate_batch_embeddings(self, contents: List[str], chunk_ids: List[str]) -> List[EmbeddingResult]:
        """Generate embeddings in batches"""
        results = []
        
        # Process in batches
        for i in tqdm(range(0, len(contents), self.batch_size), desc="Generating embeddings"):
            batch_contents = contents[i:i + self.batch_size]
            batch_ids = chunk_ids[i:i + self.batch_size]
            
            start_time = datetime.now()
            
            try:
                # Generate embeddings
                batch_embeddings = self.model.encode(
                    batch_contents,
                    batch_size=self.batch_size,
                    show_progress_bar=False,
                    convert_to_numpy=True
                )
                
                processing_time = (datetime.now() - start_time).total_seconds() * 1000
                
                # Create results
                for j, (content, chunk_id, embedding) in enumerate(zip(batch_contents, batch_ids, batch_embeddings)):
                    # Convert to list for JSON serialization
                    embedding_list = embedding.tolist()
                    
                    # Cache if enabled
                    if self.enable_caching:
                        content_hash = self._get_content_hash(content)
                        self.embedding_cache[content_hash] = embedding_list
                    
                    result = EmbeddingResult(
                        chunk_id=chunk_id,
                        embedding=embedding_list,
                        embedding_dimension=len(embedding_list),
                        model_name=self.model_name,
                        generation_timestamp=datetime.now().isoformat(),
                        processing_time_ms=processing_time / len(batch_contents),
                        cache_hit=False
                    )
                    results.append(result)
                
            except Exception as e:
                self.logger.error(f"Error generating embeddings for batch {i//self.batch_size + 1}: {str(e)}")
                # Create error results for this batch
                for chunk_id in batch_ids:
                    result = EmbeddingResult(
                        chunk_id=chunk_id,
                        embedding=[],
                        embedding_dimension=0,
                        model_name=self.model_name,
                        generation_timestamp=datetime.now().isoformat(),
                        processing_time_ms=0.0,
                        cache_hit=False
                    )
                    results.append(result)
        
        return results
    
    def _get_cached_results(self, chunks: List[Dict]) -> List[EmbeddingResult]:
        """Get results from cache"""
        cached_results = []
        
        for chunk in chunks:
            chunk_id = chunk['id']
            content = chunk['content']
            
            if self.enable_caching:
                content_hash = self._get_content_hash(content)
                if content_hash in self.embedding_cache:
                    cached_embedding = self.embedding_cache[content_hash]
                    result = EmbeddingResult(
                        chunk_id=chunk_id,
                        embedding=cached_embedding,
                        embedding_dimension=len(cached_embedding),
                        model_name=self.model_name,
                        generation_timestamp=datetime.now().isoformat(),
                        processing_time_ms=0.0,
                        cache_hit=True
                    )
                    cached_results.append(result)
        
        return cached_results
    
    def _get_content_hash(self, content: str) -> str:
        """Generate hash for content caching"""
        return hashlib.md5(content.encode()).hexdigest()
    
    def preprocess_text(self, text: str) -> str:
        """Preprocess text for better embedding quality"""
        if not text:
            return ""
        
        # Clean and normalize text
        text = text.strip()
        
        # Remove excessive whitespace
        text = ' '.join(text.split())
        
        # Ensure text is within max length
        if len(text) > self.max_length * 4:  # Rough estimate
            # Truncate to max length
            text = text[:self.max_length * 4]
            # Try to end at sentence boundary
            last_period = text.rfind('.')
            if last_period > len(text) * 0.8:  # Only if we're not cutting too much
                text = text[:last_period + 1]
        
        return text
    
    def validate_embeddings(self, results: List[EmbeddingResult]) -> Dict:
        """Validate generated embeddings"""
        validation_stats = {
            'total_embeddings': len(results),
            'successful_embeddings': 0,
            'failed_embeddings': 0,
            'cache_hits': 0,
            'cache_misses': 0,
            'avg_processing_time': 0.0,
            'dimension_consistency': True,
            'error_details': []
        }
        
        processing_times = []
        dimensions = set()
        
        for result in results:
            if result.embedding and len(result.embedding) > 0:
                validation_stats['successful_embeddings'] += 1
                dimensions.add(len(result.embedding))
                processing_times.append(result.processing_time_ms)
            else:
                validation_stats['failed_embeddings'] += 1
                validation_stats['error_details'].append({
                    'chunk_id': result.chunk_id,
                    'error': 'Empty or invalid embedding'
                })
            
            if result.cache_hit:
                validation_stats['cache_hits'] += 1
            else:
                validation_stats['cache_misses'] += 1
        
        # Check dimension consistency
        if len(dimensions) > 1:
            validation_stats['dimension_consistency'] = False
            validation_stats['error_details'].append({
                'error': f'Inconsistent embedding dimensions: {dimensions}'
            })
        
        # Calculate average processing time
        if processing_times:
            validation_stats['avg_processing_time'] = sum(processing_times) / len(processing_times)
        
        return validation_stats
    
    def save_embeddings(self, results: List[EmbeddingResult], output_file: str) -> None:
        """Save embeddings to file"""
        embeddings_data = []
        
        for result in results:
            embedding_dict = {
                'chunk_id': result.chunk_id,
                'embedding': result.embedding,
                'embedding_dimension': result.embedding_dimension,
                'model_name': result.model_name,
                'generation_timestamp': result.generation_timestamp,
                'processing_time_ms': result.processing_time_ms,
                'cache_hit': result.cache_hit
            }
            embeddings_data.append(embedding_dict)
        
        # Save to file
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(embeddings_data, f, indent=2)
        
        self.logger.info(f"Saved {len(embeddings_data)} embeddings to {output_file}")
    
    def load_embeddings(self, input_file: str) -> Dict[str, np.ndarray]:
        """Load embeddings from file"""
        try:
            with open(input_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            embeddings = {}
            for item in data:
                chunk_id = item['chunk_id']
                embedding = np.array(item['embedding'])
                embeddings[chunk_id] = embedding
            
            self.logger.info(f"Loaded {len(embeddings)} embeddings from {input_file}")
            return embeddings
            
        except Exception as e:
            self.logger.error(f"Failed to load embeddings from {input_file}: {str(e)}")
            return {}
    
    def get_embedding_stats(self, results: List[EmbeddingResult]) -> Dict:
        """Get statistics about embedding generation"""
        if not results:
            return {}
        
        stats = {
            'total_embeddings': len(results),
            'successful_embeddings': 0,
            'failed_embeddings': 0,
            'cache_hit_rate': 0.0,
            'avg_processing_time': 0.0,
            'total_processing_time': 0.0,
            'embedding_dimension': 0,
            'model_info': {
                'name': self.model_name,
                'device': self.device,
                'batch_size': self.batch_size
            }
        }
        
        processing_times = []
        cache_hits = 0
        
        for result in results:
            if result.embedding and len(result.embedding) > 0:
                stats['successful_embeddings'] += 1
                stats['embedding_dimension'] = result.embedding_dimension
            else:
                stats['failed_embeddings'] += 1
            
            processing_times.append(result.processing_time_ms)
            
            if result.cache_hit:
                cache_hits += 1
        
        # Calculate derived stats
        if processing_times:
            stats['avg_processing_time'] = sum(processing_times) / len(processing_times)
            stats['total_processing_time'] = sum(processing_times)
        
        if len(results) > 0:
            stats['cache_hit_rate'] = cache_hits / len(results)
        
        return stats

class EmbeddingProcessor:
    """Main processor for embedding generation"""
    
    def __init__(self, config: Dict):
        self.config = config
        self.logger = logging.getLogger(__name__)
        self.generator = EmbeddingGenerator(config.get('embedding', {}))
    
    def process_chunks(self, chunks_file: str, output_dir: str) -> str:
        """Process chunks and generate embeddings"""
        try:
            # Load chunks
            with open(chunks_file, 'r', encoding='utf-8') as f:
                chunks = json.load(f)
            
            self.logger.info(f"Loaded {len(chunks)} chunks for embedding generation")
            
            # Preprocess chunks
            processed_chunks = []
            for chunk in chunks:
                processed_chunk = chunk.copy()
                processed_chunk['content'] = self.generator.preprocess_text(chunk['content'])
                processed_chunks.append(processed_chunk)
            
            # Generate embeddings
            results = self.generator.generate_embeddings(processed_chunks)
            
            # Validate embeddings
            validation_stats = self.generator.validate_embeddings(results)
            
            # Save embeddings
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            embeddings_file = Path(output_dir) / f"embeddings_{timestamp}.json"
            self.generator.save_embeddings(results, embeddings_file.as_posix())
            
            # Save validation stats
            stats_file = Path(output_dir) / f"embedding_validation_{timestamp}.json"
            with open(stats_file, 'w', encoding='utf-8') as f:
                json.dump(validation_stats, f, indent=2)
            
            # Get generation stats
            gen_stats = self.generator.get_embedding_stats(results)
            
            self.logger.info(f"Embedding generation completed:")
            self.logger.info(f"  - Successful: {validation_stats['successful_embeddings']}")
            self.logger.info(f"  - Failed: {validation_stats['failed_embeddings']}")
            self.logger.info(f"  - Cache hit rate: {validation_stats['cache_hit_rate']:.2%}")
            self.logger.info(f"  - Avg processing time: {gen_stats['avg_processing_time']:.2f}ms")
            self.logger.info(f"  - Embeddings saved to: {embeddings_file}")
            
            return str(embeddings_file)
            
        except Exception as e:
            self.logger.error(f"Embedding processing failed: {str(e)}")
            raise
