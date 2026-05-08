"""
Chunking Strategy Implementation for Mutual Fund FAQ Assistant
Implements hybrid chunking approach combining semantic and sliding window methods
"""

import re
import logging
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime
import hashlib
import json
from pathlib import Path

@dataclass
class Chunk:
    """Represents a text chunk with metadata"""
    id: str
    content: str
    token_count: int
    chunk_type: str
    position: Dict
    context: Dict
    source_metadata: Dict
    quality_score: float = 0.0

class HybridChunkingStrategy:
    """Hybrid chunking strategy combining semantic and sliding window approaches"""
    
    def __init__(self, config: Dict):
        self.config = config
        self.logger = logging.getLogger(__name__)
        
        # Chunking parameters
        self.max_chunk_size = config.get('max_chunk_size', 500)
        self.min_chunk_size = config.get('min_chunk_size', 200)
        self.overlap_size = config.get('overlap_size', 50)
        self.chunking_strategy = config.get('chunking_strategy', 'hybrid')
        
        # Semantic chunking settings
        self.heading_tags = config.get('semantic_chunking', {}).get('section_detection', {}).get('heading_tags', 
                                                                                     ['h1', 'h2', 'h3', 'h4', 'h5', 'h6'])
        self.min_section_size = config.get('semantic_chunking', {}).get('section_detection', {}).get('min_section_size', 100)
        
        # Sliding window settings
        self.window_size = config.get('sliding_window', {}).get('window_size', 400)
        self.step_size = config.get('sliding_window', {}).get('step_size', 350)
        
        # Quality thresholds
        self.min_quality_score = config.get('quality_control', {}).get('min_quality_score', 0.6)
    
    def chunk_document(self, processed_content: Dict) -> List[Chunk]:
        """Main chunking method that applies hybrid strategy"""
        try:
            # Extract content and metadata
            content = processed_content.get('cleaned_content', '')
            metadata = processed_content.get('metadata', {})
            source_metadata = metadata.get('url_info', {})
            
            # If no cleaned content, try to use structured data and metadata
            if not content:
                content = self._create_content_from_metadata(processed_content)
            
            if not content or len(content.strip()) < 50:
                self.logger.warning(f"No content to chunk for {source_metadata.get('url', 'unknown')}")
                return []
            
            self.logger.info(f"Chunking document: {source_metadata.get('scheme_name', 'Unknown')}")
            
            # Apply hybrid chunking strategy
            if self.chunking_strategy == 'hybrid':
                chunks = self._hybrid_chunking(content, source_metadata)
            elif self.chunking_strategy == 'semantic':
                chunks = self._semantic_chunking(content, source_metadata)
            elif self.chunking_strategy == 'sliding_window':
                chunks = self._sliding_window_chunking(content, source_metadata)
            else:
                raise ValueError(f"Unknown chunking strategy: {self.chunking_strategy}")
            
            # Filter and validate chunks
            validated_chunks = self._validate_chunks(chunks)
            
            self.logger.info(f"Generated {len(validated_chunks)} chunks")
            return validated_chunks
            
        except Exception as e:
            self.logger.error(f"Error chunking document: {str(e)}")
            return []
    
    def _create_content_from_metadata(self, processed_content: Dict) -> str:
        """Create content from metadata and structured data when cleaned_content is empty"""
        metadata = processed_content.get('metadata', {})
        structured_data = processed_content.get('structured_data', {})
        
        content_parts = []
        
        # Add basic fund information
        scheme_name = metadata.get('scheme_name', '')
        if scheme_name:
            content_parts.append(f"Scheme: {scheme_name}")
        
        # Add key metrics from metadata
        nav = metadata.get('nav', '')
        if nav and nav != '.':
            content_parts.append(f"NAV: {nav}")
        
        expense_ratio = metadata.get('expense_ratio', '')
        if expense_ratio:
            content_parts.append(f"Expense Ratio: {expense_ratio}")
        
        exit_load = metadata.get('exit_load', '')
        if exit_load and exit_load != '0':
            content_parts.append(f"Exit Load: {exit_load}")
        
        aum = metadata.get('aum', '')
        if aum and aum != '.':
            content_parts.append(f"AUM: {aum}")
        
        # Add structured data if available
        if structured_data:
            meta_tags = structured_data.get('meta_tags', {})
            if meta_tags:
                description = meta_tags.get('description', '')
                if description:
                    content_parts.append(f"Description: {description}")
        
        # Add document type and source
        document_type = metadata.get('document_type', '')
        source_category = metadata.get('source_category', '')
        if document_type and source_category:
            content_parts.append(f"Document Type: {document_type} from {source_category}")
        
        return '\n'.join(content_parts)
    
    def _hybrid_chunking(self, content: str, source_metadata: Dict) -> List[Chunk]:
        """Hybrid chunking: semantic first, sliding window fallback"""
        chunks = []
        
        # First try semantic chunking
        semantic_chunks = self._semantic_chunking(content, source_metadata)
        
        # Handle oversized chunks with sliding window
        final_chunks = []
        for chunk in semantic_chunks:
            if chunk.token_count > self.max_chunk_size:
                # Split large chunk with sliding window
                sub_chunks = self._sliding_window_chunk_text(chunk.content, source_metadata, chunk.position)
                final_chunks.extend(sub_chunks)
            else:
                final_chunks.append(chunk)
        
        return final_chunks
    
    def _semantic_chunking(self, content: str, source_metadata: Dict) -> List[Chunk]:
        """Semantic chunking based on document structure"""
        chunks = []
        
        # Extract sections based on headings
        sections = self._extract_sections(content)
        
        chunk_index = 0
        for section in sections:
            if len(section['content']) < self.min_section_size:
                continue
            
            if len(section['content']) <= self.max_chunk_size * 4:  # Rough token estimate
                # Create chunk for this section
                chunk = self._create_semantic_chunk(
                    section['content'], 
                    section['title'], 
                    section['level'],
                    chunk_index,
                    source_metadata
                )
                chunks.append(chunk)
                chunk_index += 1
            else:
                # Split large section
                sub_chunks = self._split_large_section(section, chunk_index, source_metadata)
                chunks.extend(sub_chunks)
                chunk_index += len(sub_chunks)
        
        return chunks
    
    def _sliding_window_chunking(self, content: str, source_metadata: Dict) -> List[Chunk]:
        """Sliding window chunking"""
        chunks = []
        
        # Split content into paragraphs first
        paragraphs = self._split_into_paragraphs(content)
        
        # Create sliding windows
        window_chunks = self._sliding_window_chunk_text(content, source_metadata, {'document_index': 0})
        
        return window_chunks
    
    def _sliding_window_chunk_text(self, content: str, source_metadata: Dict, position: Dict) -> List[Chunk]:
        """Create sliding window chunks from text"""
        chunks = []
        
        # Simple token estimation (4 characters per token on average)
        estimated_tokens = len(content) // 4
        
        if estimated_tokens <= self.window_size:
            # Single chunk
            chunk = self._create_window_chunk(content, 0, source_metadata, position)
            chunks.append(chunk)
        else:
            # Multiple windows
            start_pos = 0
            chunk_index = 0
            
            while start_pos < len(content):
                # Calculate window end
                end_pos = min(start_pos + self.window_size * 4, len(content))
                
                # Try to break at sentence boundary
                if end_pos < len(content):
                    sentence_boundary = content.rfind('.', start_pos, end_pos)
                    if sentence_boundary > start_pos:
                        end_pos = sentence_boundary + 1
                
                # Extract window content
                window_content = content[start_pos:end_pos]
                
                if len(window_content.strip()) > self.min_chunk_size * 4:
                    chunk = self._create_window_chunk(window_content, chunk_index, source_metadata, position)
                    chunks.append(chunk)
                    chunk_index += 1
                
                # Move to next window
                start_pos += self.step_size * 4
                
                if start_pos >= len(content):
                    break
        
        return chunks
    
    def _extract_sections(self, content: str) -> List[Dict]:
        """Extract sections based on headings"""
        sections = []
        
        # Look for heading patterns
        heading_pattern = r'^([Hh][1-6]|[Hh]eading|[Ss]ection)\s*[:\s]*([^\n]+)'
        
        lines = content.split('\n')
        current_section = {'title': 'Introduction', 'level': 1, 'content': ''}
        
        for line in lines:
            line = line.strip()
            
            # Check for heading
            heading_match = re.match(heading_pattern, line)
            if heading_match:
                # Save previous section
                if current_section['content'].strip():
                    sections.append(current_section.copy())
                
                # Start new section
                current_section = {
                    'title': heading_match.group(2).strip(),
                    'level': int(heading_match.group(1)[1]) if heading_match.group(1)[0].lower() == 'h' else 1,
                    'content': ''
                }
            else:
                # Add to current section
                if current_section['content']:
                    current_section['content'] += '\n'
                current_section['content'] += line
        
        # Add last section
        if current_section['content'].strip():
            sections.append(current_section)
        
        return sections
    
    def _split_into_paragraphs(self, content: str) -> List[str]:
        """Split content into paragraphs"""
        paragraphs = []
        
        # Split by double newlines or other paragraph separators
        raw_paragraphs = re.split(r'\n\s*\n|\.\s*\n|\.\s{2,}', content)
        
        for para in raw_paragraphs:
            para = para.strip()
            if len(para) > 50:  # Skip very short paragraphs
                paragraphs.append(para)
        
        return paragraphs
    
    def _split_large_section(self, section: Dict, start_index: int, source_metadata: Dict) -> List[Chunk]:
        """Split a large section into smaller chunks"""
        chunks = []
        content = section['content']
        
        # Split by paragraphs first
        paragraphs = self._split_into_paragraphs(content)
        
        current_chunk_content = ''
        chunk_index = start_index
        
        for paragraph in paragraphs:
            # Check if adding this paragraph exceeds size limit
            test_content = current_chunk_content + '\n' + paragraph if current_chunk_content else paragraph
            estimated_tokens = len(test_content) // 4
            
            if estimated_tokens > self.max_chunk_size and current_chunk_content:
                # Create chunk from current content
                chunk = self._create_semantic_chunk(
                    current_chunk_content,
                    section['title'],
                    section['level'],
                    chunk_index,
                    source_metadata
                )
                chunks.append(chunk)
                chunk_index += 1
                
                # Start new chunk
                current_chunk_content = paragraph
            else:
                # Add to current chunk
                if current_chunk_content:
                    current_chunk_content += '\n'
                current_chunk_content += paragraph
        
        # Add final chunk
        if current_chunk_content.strip():
            chunk = self._create_semantic_chunk(
                current_chunk_content,
                section['title'],
                section['level'],
                chunk_index,
                source_metadata
            )
            chunks.append(chunk)
        
        return chunks
    
    def _create_semantic_chunk(self, content: str, section_title: str, section_level: int, 
                              chunk_index: int, source_metadata: Dict) -> Chunk:
        """Create a semantic chunk with metadata"""
        # Generate chunk ID
        chunk_id = self._generate_chunk_id(content, source_metadata, chunk_index)
        
        # Estimate token count
        token_count = len(content) // 4
        
        # Create position metadata
        position = {
            'document_index': 0,
            'section_index': chunk_index,
            'section_level': section_level,
            'chunk_sequence': chunk_index
        }
        
        # Create context metadata
        context = {
            'section_title': section_title,
            'section_level': section_level,
            'chunk_type': 'semantic_section'
        }
        
        # Create chunk
        chunk = Chunk(
            id=chunk_id,
            content=content.strip(),
            token_count=token_count,
            chunk_type='semantic_section',
            position=position,
            context=context,
            source_metadata=source_metadata
        )
        
        return chunk
    
    def _create_window_chunk(self, content: str, chunk_index: int, source_metadata: Dict, 
                           base_position: Dict) -> Chunk:
        """Create a sliding window chunk"""
        # Generate chunk ID
        chunk_id = self._generate_chunk_id(content, source_metadata, chunk_index)
        
        # Estimate token count
        token_count = len(content) // 4
        
        # Create position metadata
        position = base_position.copy()
        position.update({
            'chunk_index': chunk_index,
            'chunk_sequence': chunk_index
        })
        
        # Create context metadata
        context = {
            'chunk_type': 'sliding_window',
            'window_size': self.window_size,
            'overlap': self.overlap_size
        }
        
        # Create chunk
        chunk = Chunk(
            id=chunk_id,
            content=content.strip(),
            token_count=token_count,
            chunk_type='sliding_window',
            position=position,
            context=context,
            source_metadata=source_metadata
        )
        
        return chunk
    
    def _generate_chunk_id(self, content: str, source_metadata: Dict, chunk_index: int) -> str:
        """Generate unique chunk ID"""
        # Create content hash
        content_hash = hashlib.md5(content.encode()).hexdigest()[:8]
        
        # Get scheme name
        scheme_name = source_metadata.get('scheme_name', 'unknown').replace(' ', '_').lower()
        
        # Generate ID
        chunk_id = f"{scheme_name}_{content_hash}_{chunk_index}"
        
        return chunk_id
    
    def _validate_chunks(self, chunks: List[Chunk]) -> List[Chunk]:
        """Validate and filter chunks"""
        validated_chunks = []
        
        for chunk in chunks:
            # Calculate quality score
            quality_score = self._calculate_chunk_quality(chunk)
            chunk.quality_score = quality_score
            
            # Filter by quality
            if quality_score >= self.min_quality_score:
                validated_chunks.append(chunk)
            else:
                self.logger.debug(f"Filtered low-quality chunk: {chunk.id} (score: {quality_score})")
        
        return validated_chunks
    
    def _calculate_chunk_quality(self, chunk: Chunk) -> float:
        """Calculate quality score for a chunk"""
        score = 0.0
        
        # Length appropriateness (30%)
        if self.min_chunk_size <= chunk.token_count <= self.max_chunk_size:
            score += 0.3
        elif chunk.token_count < self.min_chunk_size:
            score += 0.1  # Penalize short chunks
        else:
            score += 0.2  # Slightly penalize long chunks
        
        # Semantic coherence (25%)
        if chunk.chunk_type == 'semantic_section':
            score += 0.25
        elif chunk.chunk_type == 'sliding_window':
            score += 0.15
        
        # Content completeness (25%)
        content_lower = chunk.content.lower()
        key_indicators = ['nav', 'expense', 'ratio', 'fund', 'scheme', 'investment', 'return', 'performance']
        indicator_count = sum(1 for indicator in key_indicators if indicator in content_lower)
        score += min(0.25, indicator_count / len(key_indicators) * 0.25)
        
        # Structure preservation (20%)
        if chunk.context.get('section_title'):
            score += 0.1
        if chunk.position.get('section_level'):
            score += 0.1
        
        return min(1.0, score)

class ChunkingProcessor:
    """Main processor for chunking documents"""
    
    def __init__(self, config: Dict):
        self.config = config
        self.logger = logging.getLogger(__name__)
        self.chunking_strategy = HybridChunkingStrategy(config.get('chunking', {}))
    
    def process_documents(self, processed_data: List[Dict]) -> List[Chunk]:
        """Process multiple documents and return all chunks"""
        all_chunks = []
        
        for i, document in enumerate(processed_data):
            self.logger.info(f"Processing document {i+1}/{len(processed_data)}")
            
            try:
                chunks = self.chunking_strategy.chunk_document(document)
                all_chunks.extend(chunks)
                
                self.logger.info(f"Generated {len(chunks)} chunks from document {i+1}")
                
            except Exception as e:
                self.logger.error(f"Error processing document {i+1}: {str(e)}")
                continue
        
        self.logger.info(f"Total chunks generated: {len(all_chunks)}")
        return all_chunks
    
    def save_chunks(self, chunks: List[Chunk], output_file: str) -> None:
        """Save chunks to file"""
        chunks_data = []
        
        for chunk in chunks:
            chunk_dict = {
                'id': chunk.id,
                'content': chunk.content,
                'token_count': chunk.token_count,
                'chunk_type': chunk.chunk_type,
                'position': chunk.position,
                'context': chunk.context,
                'source_metadata': chunk.source_metadata,
                'quality_score': chunk.quality_score
            }
            chunks_data.append(chunk_dict)
        
        # Save to file
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(chunks_data, f, indent=2, ensure_ascii=False)
        
        self.logger.info(f"Saved {len(chunks)} chunks to {output_file}")
    
    def get_chunking_stats(self, chunks: List[Chunk]) -> Dict:
        """Get statistics about chunking results"""
        if not chunks:
            return {}
        
        stats = {
            'total_chunks': len(chunks),
            'chunk_types': {},
            'token_stats': {},
            'quality_stats': {},
            'source_distribution': {}
        }
        
        # Chunk type distribution
        for chunk in chunks:
            chunk_type = chunk.chunk_type
            stats['chunk_types'][chunk_type] = stats['chunk_types'].get(chunk_type, 0) + 1
        
        # Token statistics
        token_counts = [chunk.token_count for chunk in chunks]
        stats['token_stats'] = {
            'min_tokens': min(token_counts),
            'max_tokens': max(token_counts),
            'avg_tokens': sum(token_counts) / len(token_counts),
            'total_tokens': sum(token_counts)
        }
        
        # Quality statistics
        quality_scores = [chunk.quality_score for chunk in chunks]
        stats['quality_stats'] = {
            'min_quality': min(quality_scores),
            'max_quality': max(quality_scores),
            'avg_quality': sum(quality_scores) / len(quality_scores)
        }
        
        # Source distribution
        for chunk in chunks:
            scheme_name = chunk.source_metadata.get('scheme_name', 'Unknown')
            stats['source_distribution'][scheme_name] = stats['source_distribution'].get(scheme_name, 0) + 1
        
        return stats
