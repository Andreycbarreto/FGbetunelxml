"""
Async PDF Processor
Robust asynchronous processing system for PDF NFe files with rate limiting,
retry logic, and error handling to prevent API timeouts.
"""

import os
import time
import logging
import asyncio
from typing import Dict, Any, List, Optional
from datetime import datetime
from threading import Thread
import queue
from dataclasses import dataclass
from pdf_vision_processor import PDFVisionProcessor
from pdf_multi_agent_simple import process_pdf_with_multi_agent_validation

logger = logging.getLogger(__name__)

@dataclass
class ProcessingJob:
    """Represents a PDF processing job."""
    file_id: int
    file_path: str
    original_filename: str
    user_id: str
    created_at: datetime
    retries: int = 0
    max_retries: int = 3

class AsyncPDFProcessor:
    """Asynchronous PDF processor with rate limiting and retry logic."""
    
    def __init__(self, max_concurrent_jobs=2, rate_limit_delay=5):
        self.max_concurrent_jobs = max_concurrent_jobs
        self.rate_limit_delay = rate_limit_delay  # seconds between API calls
        self.processing_queue = queue.Queue()
        self.active_jobs = {}
        self.last_api_call = 0
        self.is_running = False
        self.worker_thread = None
        self.vision_processor = PDFVisionProcessor()
        self.logger = logging.getLogger(__name__)
        
    def start_processor(self):
        """Start the async processing worker."""
        if not self.is_running:
            self.is_running = True
            self.worker_thread = Thread(target=self._process_worker, daemon=True)
            self.worker_thread.start()
            self.logger.info("Async PDF processor started")
    
    def stop_processor(self):
        """Stop the async processing worker."""
        self.is_running = False
        if self.worker_thread:
            self.worker_thread.join(timeout=30)
        self.logger.info("Async PDF processor stopped")
    
    def add_job(self, file_id: int, file_path: str, original_filename: str, user_id: str):
        """Add a new PDF processing job to the queue."""
        job = ProcessingJob(
            file_id=file_id,
            file_path=file_path,
            original_filename=original_filename,
            user_id=user_id,
            created_at=datetime.now()
        )
        self.processing_queue.put(job)
        self.logger.info(f"Added PDF processing job for file: {original_filename} (ID: {file_id})")
        
        # Start processor if not running
        if not self.is_running:
            self.start_processor()
    
    def get_queue_status(self) -> Dict[str, Any]:
        """Get current queue status."""
        return {
            'queue_size': self.processing_queue.qsize(),
            'active_jobs': len(self.active_jobs),
            'is_running': self.is_running
        }
    
    def _process_worker(self):
        """Main worker thread for processing PDF jobs."""
        self.logger.info("PDF processing worker started")
        
        while self.is_running:
            try:
                # Check if we can process more jobs
                if len(self.active_jobs) >= self.max_concurrent_jobs:
                    time.sleep(1)
                    continue
                
                # Get next job from queue
                try:
                    job = self.processing_queue.get(timeout=1)
                except queue.Empty:
                    continue
                
                # Start processing job
                self._process_job_async(job)
                
            except Exception as e:
                self.logger.error(f"Error in PDF processing worker: {str(e)}")
                time.sleep(5)  # Wait before retrying
    
    def _process_job_async(self, job: ProcessingJob):
        """Process a single PDF job asynchronously."""
        try:
            self.active_jobs[job.file_id] = job
            self.logger.info(f"Starting async processing for file: {job.original_filename}")
            
            # Rate limiting - ensure minimum delay between API calls
            time_since_last_call = time.time() - self.last_api_call
            if time_since_last_call < self.rate_limit_delay:
                sleep_time = self.rate_limit_delay - time_since_last_call
                self.logger.info(f"Rate limiting: waiting {sleep_time:.1f}s before processing {job.original_filename}")
                time.sleep(sleep_time)
            
            # Update database status to processing
            self._update_file_status(job.file_id, 'processing', f'Processing with GPT-4 Vision (attempt {job.retries + 1})')
            
            # Process the PDF
            self.last_api_call = time.time()
            result = self._process_pdf_with_retries(job)
            
            if result['success']:
                # Save to database
                self._save_processing_result(job, result)
                self.logger.info(f"Successfully processed PDF: {job.original_filename}")
            else:
                # Handle failure
                self._handle_processing_failure(job, result.get('error', 'Unknown error'))
                
        except Exception as e:
            self.logger.error(f"Error processing PDF job {job.original_filename}: {str(e)}")
            self._handle_processing_failure(job, str(e))
        finally:
            # Remove from active jobs
            self.active_jobs.pop(job.file_id, None)
    
    def _process_pdf_with_retries(self, job: ProcessingJob) -> Dict[str, Any]:
        """Process PDF with retry logic for API failures."""
        max_retries = job.max_retries
        
        for attempt in range(max_retries + 1):
            try:
                if attempt > 0:
                    # Exponential backoff for retries
                    wait_time = min(30, 2 ** attempt * 5)  # Max 30 seconds
                    self.logger.info(f"Retry {attempt}/{max_retries} for {job.original_filename} in {wait_time}s")
                    time.sleep(wait_time)
                
                # First attempt: Multi-agent validation system (if available)
                self.logger.info(f"Attempting enhanced processing for {job.original_filename}")
                multi_agent_success = False
                
                try:
                    # Try advanced multi-agent processing first  
                    from pdf_multi_agent_simple import process_pdf_with_advanced_agents
                    result = process_pdf_with_advanced_agents(job.file_path)
                    
                    if result.get('success') and result.get('confidence_score', 0) >= 75:
                        self.logger.info(f"Advanced multi-agent processing successful for {job.original_filename} (confidence: {result['confidence_score']:.1f}%)")
                        multi_agent_success = True
                        return result
                    else:
                        self.logger.warning(f"Advanced multi-agent processing had low confidence for {job.original_filename}, trying standard multi-agent")
                        
                        # Try standard multi-agent as fallback
                        from pdf_multi_agent_simple import process_pdf_with_multi_agent_validation
                        result = process_pdf_with_multi_agent_validation(job.file_path)
                        
                        if result.get('success') and result.get('confidence_score', 0) >= 70:
                            self.logger.info(f"Standard multi-agent processing successful for {job.original_filename} (confidence: {result['confidence_score']:.1f}%)")
                            multi_agent_success = True
                            return result
                        
                except Exception as e:
                    self.logger.warning(f"Multi-agent processing failed for {job.original_filename}: {str(e)}, trying single-agent fallback")
                
                # Fallback: Single-agent vision processor
                self.logger.info(f"Attempting single-agent vision processing for {job.original_filename}")
                result = self.vision_processor.process_pdf_with_vision(job.file_path)
                
                if result['success']:
                    return result
                else:
                    error_msg = result.get('error', 'Unknown error')
                    self.logger.warning(f"Vision processing failed for {job.original_filename} (attempt {attempt + 1}): {error_msg}")
                    
                    # Check if this is an API-related error that should trigger fallback
                    api_errors = ['502', 'bad gateway', 'timeout', 'rate limit', 'cloudflare', 'connection']
                    if any(err in error_msg.lower() for err in api_errors):
                        self.logger.info(f"API error detected for {job.original_filename}, trying simple processor")
                        
                        # Try fallback processor
                        try:
                            from pdf_simple_processor import PDFSimpleProcessor
                            fallback_processor = PDFSimpleProcessor()
                            fallback_result = fallback_processor.process_pdf(job.file_path)
                            if fallback_result.get('success'):
                                fallback_result['processing_note'] = 'Processed with fallback method due to API unavailability'
                                self.logger.info(f"Fallback processing successful for {job.original_filename}")
                                return fallback_result
                        except Exception as fallback_e:
                            self.logger.error(f"Fallback processing also failed for {job.original_filename}: {str(fallback_e)}")
                    
            except Exception as e:
                error_msg = str(e)
                self.logger.error(f"Exception during processing attempt {attempt + 1} for {job.original_filename}: {error_msg}")
                
                # Check if it's an API-related error that should use fallback
                api_errors = ['502', 'bad gateway', 'timeout', 'rate limit', 'cloudflare', 'connection', 'openai']
                if any(err in error_msg.lower() for err in api_errors):
                    self.logger.info(f"API error detected for {job.original_filename}, trying fallback processor")
                    
                    # Try fallback processor
                    try:
                        from pdf_simple_processor import PDFSimpleProcessor
                        fallback_processor = PDFSimpleProcessor()
                        fallback_result = fallback_processor.process_pdf(job.file_path)
                        if fallback_result.get('success'):
                            fallback_result['processing_note'] = 'Processed with fallback method due to API error'
                            self.logger.info(f"Fallback processing successful for {job.original_filename}")
                            return fallback_result
                    except Exception as fallback_e:
                        self.logger.error(f"Fallback processing also failed for {job.original_filename}: {str(fallback_e)}")
                
                # Check if it's a rate limit or timeout error for retries
                if 'timeout' in error_msg.lower() or 'rate' in error_msg.lower() or 'limit' in error_msg.lower():
                    if attempt < max_retries:
                        continue  # Retry for these types of errors
                
                # For other errors, don't retry
                return {
                    'success': False,
                    'error': error_msg,
                    'data': {}
                }
        
        return {
            'success': False,
            'error': f'Failed after {max_retries + 1} attempts',
            'data': {}
        }
    
    def _update_file_status(self, file_id: int, status: str, message: str = None):
        """Update file processing status in database."""
        try:
            from app import app, db
            from models import UploadedFile, ProcessingStatus
            
            with app.app_context():
                file_record = UploadedFile.query.get(file_id)
                if file_record:
                    if status == 'processing':
                        file_record.status = ProcessingStatus.PROCESSING
                        file_record.processing_started_at = datetime.now()
                    elif status == 'completed':
                        file_record.status = ProcessingStatus.COMPLETED
                        file_record.processing_completed_at = datetime.now()
                    elif status == 'error':
                        file_record.status = ProcessingStatus.ERROR
                        file_record.processing_completed_at = datetime.now()
                    
                    if message:
                        file_record.error_message = message
                    
                    db.session.commit()
                
        except Exception as e:
            self.logger.error(f"Error updating file status for {file_id}: {str(e)}")
    
    def _save_processing_result(self, job: ProcessingJob, result: Dict[str, Any]):
        """Save processing result to database."""
        try:
            from app import app, db
            from models import NFERecord, NFEItem, UploadedFile, ProcessingStatus
            
            with app.app_context():
                raw_data = result['data']
                
                # Create NFE record
                nfe_record = NFERecord()
                nfe_record.user_id = job.user_id
                nfe_record.uploaded_file_id = job.file_id
                
                # Set all compatible fields from raw_data
                for key, value in raw_data.items():
                    if key != 'items' and hasattr(nfe_record, key):
                        setattr(nfe_record, key, value)
                
                # Set processing info
                nfe_record.raw_xml_data = f"PDF processed with GPT-4 Vision: {job.original_filename}"
                nfe_record.ai_confidence_score = result.get('confidence_score', 0.9)
                nfe_record.ai_processing_notes = f'Processed using GPT-4 Vision (async) - Pages: {result.get("pages_processed", "unknown")}'
                
                db.session.add(nfe_record)
                db.session.flush()  # Get the ID
                
                # Create NFE items
                items_data = raw_data.get('items', [])
                self.logger.info(f"Processing {len(items_data)} items for {job.original_filename}")
                
                for i, item_data in enumerate(items_data):
                    self.logger.info(f"Item {i+1} raw data: {item_data}")
                    
                    nfe_item = NFEItem()
                    nfe_item.nfe_record_id = nfe_record.id
                    
                    # Set all compatible fields from item_data
                    fields_set = []
                    for key, value in item_data.items():
                        if hasattr(nfe_item, key):
                            setattr(nfe_item, key, value)
                            fields_set.append(f"{key}={value}")
                    
                    self.logger.info(f"Item {i+1} fields set: {fields_set}")
                    
                    # Log specifically service-related fields
                    service_fields = {
                        'codigo_servico': getattr(nfe_item, 'codigo_servico', None),
                        'codigo_atividade': getattr(nfe_item, 'codigo_atividade', None),
                        'descricao_servico': getattr(nfe_item, 'descricao_servico', None)
                    }
                    self.logger.info(f"Item {i+1} service fields: {service_fields}")
                    
                    db.session.add(nfe_item)
                
                # Update file status (within same context)  
                file_record = UploadedFile.query.get(job.file_id)
                if file_record:
                    file_record.status = ProcessingStatus.COMPLETED
                    file_record.processing_completed_at = datetime.now()
                
                db.session.commit()
                
                self.logger.info(f"Saved processing result for {job.original_filename} - Record ID: {nfe_record.id}, Items: {len(items_data)}")
            
        except Exception as e:
            self.logger.error(f"Error saving processing result for {job.original_filename}: {str(e)}")
            self._update_file_status(job.file_id, 'error', f'Database error: {str(e)}')
    
    def _handle_processing_failure(self, job: ProcessingJob, error_message: str):
        """Handle processing failure with potential retry."""
        job.retries += 1
        
        if job.retries <= job.max_retries:
            # Requeue for retry
            self.logger.info(f"Requeuing {job.original_filename} for retry ({job.retries}/{job.max_retries})")
            self.processing_queue.put(job)
        else:
            # Max retries reached
            self.logger.error(f"Max retries reached for {job.original_filename}: {error_message}")
            self._update_file_status(job.file_id, 'error', f'Processing failed after {job.max_retries} retries: {error_message}')

# Global instance
async_pdf_processor = AsyncPDFProcessor()

def start_async_processor():
    """Start the global async processor."""
    async_pdf_processor.start_processor()

def add_pdf_processing_job(file_id: int, file_path: str, original_filename: str, user_id: str):
    """Add a PDF processing job to the async queue."""
    async_pdf_processor.add_job(file_id, file_path, original_filename, user_id)

def get_processing_status() -> Dict[str, Any]:
    """Get current processing queue status."""
    return async_pdf_processor.get_queue_status()