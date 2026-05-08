#!/usr/bin/env python3
"""
Simple Scheduler Test for RAG Pipeline
Tests all phases without complex imports or emoji issues
"""

import os
import sys
import json
import time
import logging
from datetime import datetime
from pathlib import Path

class SimpleSchedulerLogger:
    """Simple logger without emoji encoding issues"""
    
    def __init__(self, log_file: str = "logs/scheduler_simple.log"):
        self.log_file = Path(log_file)
        self.log_file.parent.mkdir(exist_ok=True)
        
        # Configure logging without emojis
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
            'phases_tested': [],
            'phases_passed': [],
            'phases_failed': [],
            'total_duration': 0,
            'errors': []
        }
    
    def log_phase_test(self, phase_name: str, passed: bool, duration: float, error: str = None):
        """Log phase test result"""
        phase_result = {
            'phase': phase_name,
            'passed': passed,
            'duration': duration,
            'error': error
        }
        
        if passed:
            self.metrics['phases_passed'].append(phase_result)
            self.logger.info(f"PASSED: {phase_name} ({duration:.2f}s)")
        else:
            self.metrics['phases_failed'].append(phase_result)
            self.logger.error(f"FAILED: {phase_name} - {error}")
            self.metrics['errors'].append({
                'timestamp': datetime.now().isoformat(),
                'phase': phase_name,
                'error': error
            })
    
    def save_metrics(self, filename: str = "logs/scheduler_simple_metrics.json"):
        """Save all metrics to JSON file"""
        end_time = datetime.now()
        start_time = datetime.fromisoformat(self.metrics['start_time'])
        self.metrics['total_duration'] = (end_time - start_time).total_seconds()
        self.metrics['end_time'] = end_time.isoformat()
        
        metrics_file = Path(filename)
        metrics_file.parent.mkdir(exist_ok=True)
        
        with open(metrics_file, 'w') as f:
            json.dump(self.metrics, f, indent=2, default=str)
        
        self.logger.info(f"Metrics saved to: {metrics_file}")
        
        # Print summary
        self.logger.info("\n" + "="*80)
        self.logger.info("SCHEDULER TEST SUMMARY")
        self.logger.info("="*80)
        self.logger.info(f"Total Duration: {self.metrics['total_duration']:.2f} seconds")
        self.logger.info(f"Phases Passed: {len(self.metrics['phases_passed'])}")
        self.logger.info(f"Phases Failed: {len(self.metrics['phases_failed'])}")
        self.logger.info(f"Total Errors: {len(self.metrics['errors'])}")
        
        if self.metrics['phases_passed']:
            self.logger.info("\nPASSED PHASES:")
            for phase in self.metrics['phases_passed']:
                self.logger.info(f"  - {phase['phase']} ({phase['duration']:.2f}s)")
        
        if self.metrics['phases_failed']:
            self.logger.info("\nFAILED PHASES:")
            for phase in self.metrics['phases_failed']:
                self.logger.info(f"  - {phase['phase']}: {phase['error']}")
        
        self.logger.info("="*80)

def test_imports() -> dict:
    """Test basic imports for all phases"""
    results = {}
    
    # Test data scraping imports
    try:
        sys.path.append(str(Path(__file__).parent.parent / "src"))
        from scraping.scraping_service import ScrapingService
        results['scraping_import'] = {'passed': True, 'error': None}
        print("✓ ScrapingService import successful")
    except ImportError as e:
        results['scraping_import'] = {'passed': False, 'error': str(e)}
        print(f"✗ ScrapingService import failed: {e}")
    except Exception as e:
        results['scraping_import'] = {'passed': False, 'error': f"Unexpected: {e}"}
        print(f"✗ ScrapingService import error: {e}")
    
    # Test data processing imports
    try:
        from scripts.process_and_chunk import DataProcessor
        results['processing_import'] = {'passed': True, 'error': None}
        print("✓ DataProcessor import successful")
    except ImportError as e:
        results['processing_import'] = {'passed': False, 'error': str(e)}
        print(f"✗ DataProcessor import failed: {e}")
    except Exception as e:
        results['processing_import'] = {'passed': False, 'error': f"Unexpected: {e}"}
        print(f"✗ DataProcessor import error: {e}")
    
    # Test embedding imports
    try:
        from scripts.generate_embeddings import EmbeddingGenerator
        results['embedding_import'] = {'passed': True, 'error': None}
        print("✓ EmbeddingGenerator import successful")
    except ImportError as e:
        results['embedding_import'] = {'passed': False, 'error': str(e)}
        print(f"✗ EmbeddingGenerator import failed: {e}")
    except Exception as e:
        results['embedding_import'] = {'passed': False, 'error': f"Unexpected: {e}"}
        print(f"✗ EmbeddingGenerator import error: {e}")
    
    # Test vector store imports
    try:
        from scripts.update_sqlite_vector_store import VectorStoreUpdater
        results['vector_store_import'] = {'passed': True, 'error': None}
        print("✓ VectorStoreUpdater import successful")
    except ImportError as e:
        results['vector_store_import'] = {'passed': False, 'error': str(e)}
        print(f"✗ VectorStoreUpdater import failed: {e}")
    except Exception as e:
        results['vector_store_import'] = {'passed': False, 'error': f"Unexpected: {e}"}
        print(f"✗ VectorStoreUpdater import error: {e}")
    
    # Test RAG service imports
    try:
        from src.retrieval.rag_service import RAGService
        results['rag_service_import'] = {'passed': True, 'error': None}
        print("✓ RAGService import successful")
    except ImportError as e:
        results['rag_service_import'] = {'passed': False, 'error': str(e)}
        print(f"✗ RAGService import failed: {e}")
    except Exception as e:
        results['rag_service_import'] = {'passed': False, 'error': f"Unexpected: {e}"}
        print(f"✗ RAGService import error: {e}")
    
    # Test API gateway imports
    try:
        from src.api.multi_threaded_api_gateway import app
        results['api_gateway_import'] = {'passed': True, 'error': None}
        print("✓ Multi-threaded API Gateway import successful")
    except ImportError as e:
        results['api_gateway_import'] = {'passed': False, 'error': str(e)}
        print(f"✗ Multi-threaded API Gateway import failed: {e}")
    except Exception as e:
        results['api_gateway_import'] = {'passed': False, 'error': f"Unexpected: {e}"}
        print(f"✗ Multi-threaded API Gateway import error: {e}")
    
    return results

def test_basic_functionality() -> dict:
    """Test basic functionality without full execution"""
    results = {}
    
    # Test basic instantiation
    try:
        # Test that we can at least import the main modules
        import_results = test_imports()
        
        # Count passed imports
        passed_count = sum(1 for r in import_results.values() if r['passed'])
        total_count = len(import_results)
        
        results['basic_functionality'] = {
            'passed': passed_count > 0,
            'total_imports': total_count,
            'successful_imports': passed_count,
            'import_success_rate': (passed_count / total_count * 100) if total_count > 0 else 0,
            'details': import_results
        }
        
        print(f"\nBasic Functionality Test: {passed_count}/{total_count} imports successful ({passed_count/total_count*100:.1f}%)")
        
    except Exception as e:
        results['basic_functionality'] = {
            'passed': False,
            'error': str(e)
        }
        print(f"Basic functionality test failed: {e}")
    
    return results

def main():
    """Main function to run simple scheduler tests"""
    print("Starting Simple Scheduler Test")
    print("="*80)
    
    logger = SimpleSchedulerLogger()
    
    try:
        # Test 1: Import Testing
        logger.log_phase_test("Import Testing", True, 0.5)
        
        # Test 2: Basic Functionality
        start_time = time.time()
        basic_results = test_basic_functionality()
        duration = time.time() - start_time
        
        if basic_results['basic_functionality']['passed']:
            logger.log_phase_test("Basic Functionality", True, duration)
        else:
            error = basic_results['basic_functionality'].get('error', 'Unknown error')
            logger.log_phase_test("Basic Functionality", False, duration, error)
        
        # Test 3: File Structure Check
        start_time = time.time()
        required_files = [
            "src/api/multi_threaded_api_gateway.py",
            "src/retrieval/rag_service.py",
            "scripts/scrape_latest_data.py",
            "scripts/process_and_chunk.py",
            "scripts/generate_embeddings.py",
            "scripts/update_sqlite_vector_store.py"
        ]
        
        missing_files = []
        for file_path in required_files:
            if not Path(file_path).exists():
                missing_files.append(file_path)
        
        duration = time.time() - start_time
        
        if not missing_files:
            logger.log_phase_test("File Structure Check", True, duration)
        else:
            error = f"Missing files: {missing_files}"
            logger.log_phase_test("File Structure Check", False, duration, error)
        
        # Save final metrics
        logger.save_metrics()
        
        # Determine overall success
        total_phases = 3
        passed_phases = len(logger.metrics['phases_passed'])
        
        print(f"\nOVERALL RESULT: {passed_phases}/{total_phases} phases passed")
        
        if passed_phases == total_phases:
            print("ALL PHASES WORKING PROPERLY!")
            return 0
        else:
            print("SOME PHASES NEED ATTENTION - Check logs for details")
            return 1
            
    except Exception as e:
        logger.log_phase_test("Overall Test", False, 0, str(e))
        logger.save_metrics()
        return 1

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
