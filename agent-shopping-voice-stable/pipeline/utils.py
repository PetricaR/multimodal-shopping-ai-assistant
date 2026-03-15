"""
Pipeline Utilities
Helper functions for the data pipeline
"""
import logging
import sys
import time
from functools import wraps

import os

def setup_pipeline_logging(name: str):
    """Configure logging for the pipeline"""
    # Ensure logs directory exists
    log_dir = "logs"
    os.makedirs(log_dir, exist_ok=True)
    
    # Check if handlers are already configured to avoid duplication
    logger = logging.getLogger(name)
    if logger.hasHandlers():
        return logger
        
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler(f'{log_dir}/pipeline_{name}.log')
        ]
    )
    return logging.getLogger(name)

def timer(func):
    """Decorator to time pipeline steps"""
    @wraps(func)
    def wrapper(*args, **kwargs):
        start_time = time.time()
        logger = logging.getLogger("pipeline")
        step_name = func.__name__.replace("_", " ").title()
        
        logger.info(f"\n{'='*50}\n▶ STARTING: {step_name}\n{'='*50}")
        try:
            result = func(*args, **kwargs)
            duration = time.time() - start_time
            logger.info(f"✔ COMPLETED: {step_name} in {duration:.2f}s\n")
            return result
        except Exception as e:
            duration = time.time() - start_time
            logger.error(f"❌ FAILED: {step_name} after {duration:.2f}s - error: {e}\n")
            raise
    return wrapper
