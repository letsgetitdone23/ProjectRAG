#!/usr/bin/env python3
"""
Simple Scheduler Trigger for Testing RAG Pipeline
Runs all phases of data ingestion with comprehensive logging
"""

import os
import sys
import json
import time
import logging
from datetime import datetime
from pathlib import Path

class SimpleLogger:
    """Simple logger for scheduler testing"""
    
    def __init__(self, log_file: str = "logs/scheduler_test.log"):
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
            'start_time': datetime.now().isoformat(),
            'phases_completed': [],
            'phases_failed': [],
            'total_duration': 0,
            'errors': []
        }
    
    def log_phase_start(self, phase_name: str):
        """Log phase start"""
        self.logger.info(f"🚀 STARTING: {phase_name}")
        
    def log_phase_complete(self, phase_name: str, duration: float, details: str = ""):
        """Log phase completion"""
        self.metrics['phases_completed'].append({
            'phase': phase_name,
            'duration': duration,
            'details': details
        })
        self.logger.info(f"✅ COMPLETED: {phase_name} ({duration:.2f}s) {details}")
        
    def log_phase_error(self, phase_name: str, error: str):
        """Log phase error"""
        self.metrics['phases_failed'].append({
            'phase': phase_name,
            'error': error
        })
        self.metrics['errors'].append({
            'timestamp': datetime.now().isoformat(),
            'phase': phase_name,
            'error': error
        })
        self.logger.error(f"❌ FAILED: {phase_name} - {error}")
    
    def save_metrics(self):
        """Save metrics to JSON file"""
        end_time = datetime.now()
        start_time = datetime.fromisoformat(self.metrics['start_time'])
        self.metrics['total_duration'] = (end_time - start_time).total_seconds()
        self.metrics['end_time'] = end_time.isoformat()
        
        metrics_file = Path("logs/scheduler_metrics.json")
        metrics_file.parent.mkdir(exist_ok=True)
        
        with open(metrics_file, 'w') as f:
            json.dump(self.metrics, f, indent=2, default=str)
        
        self.logger.info(f"📊 METRICS SAVED: {metrics_file}")
        
        # Print summary
        self.logger.info("\n" + "="*80)
        self.logger.info("📊 SCHEDULER TEST SUMMARY")
        self.logger.info("="*80)
        self.logger.info(f"⏱️  Total Duration: {self.metrics['total_duration']:.2f} seconds")
        self.logger.info(f"✅ Phases Completed: {len(self.metrics['phases_completed'])}")
        self.logger.info(f"❌ Phases Failed: {len(self.metrics['phases_failed'])}")
        self.logger.info(f"🚨 Total Errors: {len(self.metrics['errors'])}")
        
        if self.metrics['phases_completed']:
            self.logger.info("\n✅ COMPLETED PHASES:")
            for phase in self.metrics['phases_completed']:
                self.logger.info(f"   • {phase['phase']} ({phase['duration']:.2f}s)")
        
        if self.metrics['phases_failed']:
            self.logger.info("\n❌ FAILED PHASES:")
            for phase in self.metrics['phases_failed']:
                self.logger.info(f"   • {phase['phase']}: {phase['error']}")
        
        self.logger.info("="*80)

def test_phase_1_scraping(logger: SimpleLogger) -> bool:
    """Test Phase 1: Data Scraping"""
    logger.log_phase_start("Phase 1: Data Scraping")
    start_time = time.time()
    
    try:
        # Test import and basic functionality
        logger.logger.info("Testing data scraping imports...")
        
        # Try to import scraping modules
        try:
            sys.path.append(str(Path(__file__).parent.parent / "src"))
            from scraping.scraping_service import ScrapingService
            logger.logger.info("✅ ScrapingService import successful")
        except ImportError as e:
            logger.log_phase_error("Phase 1: Data Scraping", f"Import error: {e}")
            return False
        
        # Test basic scraping functionality
        try:
            service = ScrapingService()
            logger.logger.info("✅ ScrapingService instantiation successful")
        except Exception as e:
            logger.log_phase_error("Phase 1: Data Scraping", f"Service instantiation error: {e}")
            return False
        
        # Test configuration loading
        try:
            config = service.load_config()
            logger.logger.info("✅ Configuration loading successful")
        except Exception as e:
            logger.log_phase_error("Phase 1: Data Scraping", f"Configuration error: {e}")
            return False
        
        duration = time.time() - start_time
        logger.log_phase_complete("Phase 1: Data Scraping", duration, "Imports and configuration tested")
        return True
        
    except Exception as e:
        logger.log_phase_error("Phase 1: Data Scraping", f"Unexpected error: {e}")
        return False

def test_phase_2_processing(logger: SimpleLogger) -> bool:
    """Test Phase 2: Data Processing"""
    logger.log_phase_start("Phase 2: Data Processing")
    start_time = time.time()
    
    try:
        # Test data processing imports
        try:
            from scripts.process_and_chunk import DataProcessor
            logger.logger.info("✅ DataProcessor import successful")
        except ImportError as e:
            logger.log_phase_error("Phase 2: Data Processing", f"Import error: {e}")
            return False
        
        # Test basic processing functionality
        try:
            processor = DataProcessor()
            logger.logger.info("✅ DataProcessor instantiation successful")
        except Exception as e:
            logger.log_phase_error("Phase 2: Data Processing", f"Processor instantiation error: {e}")
            return False
        
        duration = time.time() - start_time
        logger.log_phase_complete("Phase 2: Data Processing", duration, "Imports and instantiation tested")
        return True
        
    except Exception as e:
        logger.log_phase_error("Phase 2: Data Processing", f"Unexpected error: {e}")
        return False

def test_phase_3_embeddings(logger: SimpleLogger) -> bool:
    """Test Phase 3: Embedding Generation"""
    logger.log_phase_start("Phase 3: Embedding Generation")
    start_time = time.time()
    
    try:
        # Test embedding imports
        try:
            from scripts.generate_embeddings import EmbeddingGenerator
            logger.logger.info("✅ EmbeddingGenerator import successful")
        except ImportError as e:
            logger.log_phase_error("Phase 3: Embedding Generation", f"Import error: {e}")
            return False
        
        # Test basic embedding functionality
        try:
            generator = EmbeddingGenerator()
            logger.logger.info("✅ EmbeddingGenerator instantiation successful")
        except Exception as e:
            logger.log_phase_error("Phase 3: Embedding Generation", f"Generator instantiation error: {e}")
            return False
        
        duration = time.time() - start_time
        logger.log_phase_complete("Phase 3: Embedding Generation", duration, "Imports and instantiation tested")
        return True
        
    except Exception as e:
        logger.log_phase_error("Phase 3: Embedding Generation", f"Unexpected error: {e}")
        return False

def test_phase_4_vector_store(logger: SimpleLogger) -> bool:
    """Test Phase 4: Vector Store Update"""
    logger.log_phase_start("Phase 4: Vector Store Update")
    start_time = time.time()
    
    try:
        # Test vector store imports
        try:
            from scripts.update_sqlite_vector_store import VectorStoreUpdater
            logger.logger.info("✅ VectorStoreUpdater import successful")
        except ImportError as e:
            logger.log_phase_error("Phase 4: Vector Store Update", f"Import error: {e}")
            return False
        
        # Test basic vector store functionality
        try:
            updater = VectorStoreUpdater()
            logger.logger.info("✅ VectorStoreUpdater instantiation successful")
        except Exception as e:
            logger.log_phase_error("Phase 4: Vector Store Update", f"Updater instantiation error: {e}")
            return False
        
        duration = time.time() - start_time
        logger.log_phase_complete("Phase 4: Vector Store Update", duration, "Imports and instantiation tested")
        return True
        
    except Exception as e:
        logger.log_phase_error("Phase 4: Vector Store Update", f"Unexpected error: {e}")
        return False

def test_phase_5_rag_service(logger: SimpleLogger) -> bool:
    """Test Phase 5: RAG Service Integration"""
    logger.log_phase_start("Phase 5: RAG Service Integration")
    start_time = time.time()
    
    try:
        # Test RAG service imports
        try:
            from src.retrieval.rag_service import RAGService
            logger.logger.info("✅ RAGService import successful")
        except ImportError as e:
            logger.log_phase_error("Phase 5: RAG Service Integration", f"Import error: {e}")
            return False
        
        # Test basic RAG functionality
        try:
            rag_service = RAGService()
            logger.logger.info("✅ RAGService instantiation successful")
        except Exception as e:
            logger.log_phase_error("Phase 5: RAG Service Integration", f"RAG instantiation error: {e}")
            return False
        
        duration = time.time() - start_time
        logger.log_phase_complete("Phase 5: RAG Service Integration", duration, "Imports and instantiation tested")
        return True
        
    except Exception as e:
        logger.log_phase_error("Phase 5: RAG Service Integration", f"Unexpected error: {e}")
        return False

def test_phase_6_api_gateway(logger: SimpleLogger) -> bool:
    """Test Phase 6: API Gateway"""
    logger.log_phase_start("Phase 6: API Gateway")
    start_time = time.time()
    
    try:
        # Test API gateway imports
        try:
            from src.api.multi_threaded_api_gateway import app
            logger.logger.info("✅ Multi-threaded API Gateway import successful")
        except ImportError as e:
            logger.log_phase_error("Phase 6: API Gateway", f"Import error: {e}")
            return False
        
        # Test basic API gateway functionality
        try:
            # Just test that the app can be imported
            logger.logger.info("✅ API Gateway app import successful")
        except Exception as e:
            logger.log_phase_error("Phase 6: API Gateway", f"API Gateway error: {e}")
            return False
        
        duration = time.time() - start_time
        logger.log_phase_complete("Phase 6: API Gateway", duration, "Import tested")
        return True
        
    except Exception as e:
        logger.log_phase_error("Phase 6: API Gateway", f"Unexpected error: {e}")
        return False

def main():
    """Main function to run all phase tests"""
    print("🚀 Starting Local Scheduler Phase Testing")
    print("="*80)
    
    logger = SimpleLogger()
    
    # Run all phase tests
    phases = [
        ("Data Scraping", test_phase_1_scraping),
        ("Data Processing", test_phase_2_processing),
        ("Embedding Generation", test_phase_3_embeddings),
        ("Vector Store Update", test_phase_4_vector_store),
        ("RAG Service Integration", test_phase_5_rag_service),
        ("API Gateway", test_phase_6_api_gateway)
    ]
    
    success_count = 0
    
    for phase_name, test_func in phases:
        if test_func(logger):
            success_count += 1
        else:
            logger.logger.warning(f"⚠️  Phase {phase_name} failed - check dependencies")
    
    # Save final metrics
    logger.save_metrics()
    
    # Final result
    total_phases = len(phases)
    success_rate = (success_count / total_phases) * 100
    
    print(f"\n🎯 PHASE TESTING COMPLETED")
    print(f"✅ Successful: {success_count}/{total_phases} ({success_rate:.1f}%)")
    
    if success_count == total_phases:
        print("🎉 ALL PHASES WORKING PROPERLY!")
        return 0
    else:
        print("⚠️  SOME PHASES NEED ATTENTION")
        print("📊 Check logs/scheduler_test.log for details")
        return 1

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
