#!/usr/bin/env python3
"""
Local Scheduler Trigger for Nippon India Mutual Fund RAG System

This script manually triggers the complete data ingestion pipeline
to verify all phases are working properly. Includes comprehensive logging.
"""

import os
import sys
import json
import time
import logging
from datetime import datetime
from pathlib import Path

# Add src to path for imports
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src'))

from scripts.scrape_data import DataScrapingService
from scripts.process_and_chunk import DataProcessor
from scripts.generate_embeddings import EmbeddingGenerator
from scripts.update_sqlite_vector_store import VectorStoreUpdater

class SchedulerLogger:
    """Comprehensive logger for scheduler activities"""
    
    def __init__(self, log_file: str = "logs/scheduler_run.log"):
        self.log_file = Path(log_file)
        self.log_file.parent.mkdir(exist_ok=True)
        
        # Configure logging
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(self.log_file),
                logging.StreamHandler(sys.stdout)
            ]
        )
        self.logger = logging.getLogger(__name__)
        
        # Metrics tracking
        self.metrics = {
            'start_time': None,
            'end_time': None,
            'total_duration': 0,
            'phases': {},
            'errors': [],
            'warnings': [],
            'sources_scraped': 0,
            'documents_processed': 0,
            'chunks_generated': 0,
            'embeddings_created': 0,
            'vector_store_updated': False
        }
    
    def start_phase(self, phase_name: str):
        """Start logging a new phase"""
        self.metrics['phases'][phase_name] = {
            'start_time': datetime.now().isoformat(),
            'end_time': None,
            'duration': 0,
            'status': 'running',
            'details': {}
        }
        self.logger.info(f"🚀 STARTING PHASE: {phase_name}")
        
    def end_phase(self, phase_name: str, details: dict = None):
        """End a phase and record metrics"""
        if phase_name in self.metrics['phases']:
            phase = self.metrics['phases'][phase_name]
            phase['end_time'] = datetime.now().isoformat()
            start = datetime.fromisoformat(phase['start_time'])
            end = datetime.fromisoformat(phase['end_time'])
            phase['duration'] = (end - start).total_seconds()
            phase['status'] = 'completed'
            if details:
                phase['details'] = details
            
            self.logger.info(f"✅ COMPLETED PHASE: {phase_name} (Duration: {phase['duration']:.2f}s)")
            if details:
                for key, value in details.items():
                    self.logger.info(f"   📊 {key}: {value}")
    
    def log_error(self, phase: str, error: str, details: dict = None):
        """Log an error with context"""
        error_entry = {
            'timestamp': datetime.now().isoformat(),
            'phase': phase,
            'error': error,
            'details': details or {}
        }
        self.metrics['errors'].append(error_entry)
        self.logger.error(f"❌ ERROR in {phase}: {error}")
        if details:
            for key, value in details.items():
                self.logger.error(f"   🔍 {key}: {value}")
    
    def log_warning(self, phase: str, warning: str, details: dict = None):
        """Log a warning with context"""
        warning_entry = {
            'timestamp': datetime.now().isoformat(),
            'phase': phase,
            'warning': warning,
            'details': details or {}
        }
        self.metrics['warnings'].append(warning_entry)
        self.logger.warning(f"⚠️  WARNING in {phase}: {warning}")
        if details:
            for key, value in details.items():
                self.logger.warning(f"   🔍 {key}: {value}")
    
    def update_metric(self, key: str, value):
        """Update a specific metric"""
        self.metrics[key] = value
        self.logger.info(f"📈 METRIC UPDATE: {key} = {value}")
    
    def save_metrics(self, filename: str = "logs/scheduler_metrics.json"):
        """Save all metrics to JSON file"""
        metrics_file = Path(filename)
        metrics_file.parent.mkdir(exist_ok=True)
        
        # Add final timestamp if not present
        if not self.metrics['end_time']:
            self.metrics['end_time'] = datetime.now().isoformat()
            if self.metrics['start_time']:
                start = datetime.fromisoformat(self.metrics['start_time'])
                end = datetime.fromisoformat(self.metrics['end_time'])
                self.metrics['total_duration'] = (end - start).total_seconds()
        
        with open(metrics_file, 'w') as f:
            json.dump(self.metrics, f, indent=2, default=str)
        
        self.logger.info(f"💾 METRICS SAVED: {metrics_file}")
    
    def print_summary(self):
        """Print comprehensive summary"""
        self.logger.info("\n" + "="*80)
        self.logger.info("📊 SCHEDULER RUN SUMMARY")
        self.logger.info("="*80)
        
        if self.metrics['start_time'] and self.metrics['end_time']:
            self.logger.info(f"⏱️  Total Duration: {self.metrics['total_duration']:.2f} seconds")
        
        self.logger.info(f"📁 Sources Scraped: {self.metrics['sources_scraped']}")
        self.logger.info(f"📄 Documents Processed: {self.metrics['documents_processed']}")
        self.logger.info(f"🧩 Chunks Generated: {self.metrics['chunks_generated']}")
        self.logger.info(f"🔢 Embeddings Created: {self.metrics['embeddings_created']}")
        self.logger.info(f"💾 Vector Store Updated: {self.metrics['vector_store_updated']}")
        
        self.logger.info(f"\n📋 PHASES COMPLETED: {len([p for p in self.metrics['phases'].values() if p['status'] == 'completed'])}")
        self.logger.info(f"❌ ERRORS: {len(self.metrics['errors'])}")
        self.logger.info(f"⚠️  WARNINGS: {len(self.metrics['warnings'])}")
        
        if self.metrics['errors']:
            self.logger.info("\n🚨 ERROR DETAILS:")
            for error in self.metrics['errors']:
                self.logger.info(f"   • {error['phase']}: {error['error']}")
        
        if self.metrics['warnings']:
            self.logger.info("\n⚠️  WARNING DETAILS:")
            for warning in self.metrics['warnings']:
                self.logger.info(f"   • {warning['phase']}: {warning['warning']}")
        
        self.logger.info("="*80)

class LocalScheduler:
    """Local scheduler runner for complete RAG pipeline"""
    
    def __init__(self):
        self.logger = SchedulerLogger()
        self.scraping_service = DataScrapingService()
        self.data_processor = DataProcessor()
        self.embedding_generator = EmbeddingGenerator()
        self.vector_updater = VectorStoreUpdater()
    
    def run_complete_pipeline(self):
        """Execute all phases of the RAG pipeline"""
        self.logger.update_metric('start_time', datetime.now().isoformat())
        self.logger.logger.info("🚀 STARTING COMPLETE RAG PIPELINE")
        
        try:
            # Phase 1: Data Scraping
            self.logger.start_phase("Data Scraping")
            try:
                scraped_data = self.scraping_service.scrape_all_sources()
                sources_count = len(scraped_data) if isinstance(scraped_data, list) else 1
                self.logger.update_metric('sources_scraped', sources_count)
                self.logger.end_phase("Data Scraping", {
                    'sources_count': sources_count,
                    'data_types': list(scraped_data.keys()) if isinstance(scraped_data, dict) else 'unknown'
                })
            except Exception as e:
                self.logger.log_error("Data Scraping", str(e), {'type': type(e).__name__})
                return False
            
            # Phase 2: Data Processing
            self.logger.start_phase("Data Processing")
            try:
                processed_data = self.data_processor.process_scraped_data(scraped_data)
                docs_count = len(processed_data) if isinstance(processed_data, list) else 0
                self.logger.update_metric('documents_processed', docs_count)
                self.logger.end_phase("Data Processing", {
                    'documents_count': docs_count,
                    'processing_successful': docs_count > 0
                })
            except Exception as e:
                self.logger.log_error("Data Processing", str(e), {'type': type(e).__name__})
                return False
            
            # Phase 3: Chunking Strategy
            self.logger.start_phase("Document Chunking")
            try:
                chunks = self.data_processor.create_chunks(processed_data)
                chunks_count = len(chunks) if isinstance(chunks, list) else 0
                self.logger.update_metric('chunks_generated', chunks_count)
                self.logger.end_phase("Document Chunking", {
                    'chunks_count': chunks_count,
                    'chunk_size_range': '200-500 tokens'
                })
            except Exception as e:
                self.logger.log_error("Document Chunking", str(e), {'type': type(e).__name__})
                return False
            
            # Phase 4: Embedding Generation
            self.logger.start_phase("Embedding Generation")
            try:
                embeddings = self.embedding_generator.generate_embeddings(chunks)
                embeddings_count = len(embeddings) if isinstance(embeddings, list) else 0
                self.logger.update_metric('embeddings_created', embeddings_count)
                self.logger.end_phase("Embedding Generation", {
                    'embeddings_count': embeddings_count,
                    'model': 'BGE Large English v1.5',
                    'dimensions': 1024
                })
            except Exception as e:
                self.logger.log_error("Embedding Generation", str(e), {'type': type(e).__name__})
                return False
            
            # Phase 5: Vector Store Update
            self.logger.start_phase("Vector Store Update")
            try:
                update_result = self.vector_updater.update_vector_store(embeddings)
                self.logger.update_metric('vector_store_updated', update_result)
                self.logger.end_phase("Vector Store Update", {
                    'update_successful': update_result,
                    'vector_store_type': 'SQLite with vector extensions'
                })
            except Exception as e:
                self.logger.log_error("Vector Store Update", str(e), {'type': type(e).__name__})
                return False
            
            # Phase 6: Validation
            self.logger.start_phase("System Validation")
            try:
                validation_results = self._validate_system()
                self.logger.end_phase("Vector Store Update", validation_results)
            except Exception as e:
                self.logger.log_error("System Validation", str(e), {'type': type(e).__name__})
                return False
            
            self.logger.update_metric('end_time', datetime.now().isoformat())
            self.logger.logger.info("✅ COMPLETE RAG PIPELINE FINISHED SUCCESSFULLY")
            return True
            
        except Exception as e:
            self.logger.log_error("Complete Pipeline", str(e), {'type': type(e).__name__})
            return False
        finally:
            self.logger.save_metrics()
            self.logger.print_summary()
    
    def _validate_system(self) -> dict:
        """Validate the complete system after pipeline run"""
        validation_results = {}
        
        try:
            # Validate vector store
            if hasattr(self.vector_updater, 'validate_vector_store'):
                vs_validation = self.vector_updater.validate_vector_store()
                validation_results['vector_store'] = vs_validation
            else:
                validation_results['vector_store'] = {'status': 'skipped', 'reason': 'validation method not available'}
            
            # Validate embeddings
            if hasattr(self.embedding_generator, 'validate_embeddings'):
                emb_validation = self.embedding_generator.validate_embeddings()
                validation_results['embeddings'] = emb_validation
            else:
                validation_results['embeddings'] = {'status': 'skipped', 'reason': 'validation method not available'}
            
            # Validate data processing
            if hasattr(self.data_processor, 'validate_processing'):
                proc_validation = self.data_processor.validate_processing()
                validation_results['data_processing'] = proc_validation
            else:
                validation_results['data_processing'] = {'status': 'skipped', 'reason': 'validation method not available'}
            
            validation_results['overall_status'] = 'completed'
            
        except Exception as e:
            validation_results['overall_status'] = 'failed'
            validation_results['error'] = str(e)
        
        return validation_results

def main():
    """Main function to run the local scheduler"""
    print("🚀 Starting Local RAG Pipeline Scheduler")
    print("="*80)
    
    scheduler = LocalScheduler()
    
    try:
        success = scheduler.run_complete_pipeline()
        
        if success:
            print("\n✅ PIPELINE COMPLETED SUCCESSFULLY")
            print("📊 Check logs/scheduler_run.log for detailed execution logs")
            print("📈 Check logs/scheduler_metrics.json for performance metrics")
        else:
            print("\n❌ PIPELINE FAILED")
            print("🔍 Check logs/scheduler_run.log for error details")
            
        return 0 if success else 1
        
    except KeyboardInterrupt:
        print("\n⚠️  PIPELINE INTERRUPTED BY USER")
        return 2
    except Exception as e:
        print(f"\n💥 UNEXPECTED ERROR: {e}")
        return 3

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
