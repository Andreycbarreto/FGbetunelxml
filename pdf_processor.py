"""
PDF NFe Processor
Processes NFe PDF files and converts them to structured markdown for AI processing.
"""

import os
import logging
import pymupdf4llm
import fitz  # PyMuPDF
from typing import Dict, Any, Optional
import re

logger = logging.getLogger(__name__)

class NFEPDFProcessor:
    """Processes NFe PDF files and extracts structured data."""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    def process_pdf_file(self, file_path: str) -> Dict[str, Any]:
        """
        Process an NFe PDF file and extract structured markdown.
        
        Args:
            file_path (str): Path to the PDF file
            
        Returns:
            dict: Contains markdown content and metadata for AI processing
        """
        try:
            self.logger.info(f"Starting PDF processing for: {file_path}")
            
            # Extract text and structure using pymupdf4llm
            markdown_content = self._extract_structured_markdown(file_path)
            
            # Extract basic metadata
            metadata = self._extract_pdf_metadata(file_path)
            
            # Prepare data structure for AI processing
            result = {
                'markdown_content': markdown_content,
                'metadata': metadata,
                'file_path': file_path,
                'processing_method': 'pdf_to_markdown',
                'success': True
            }
            
            self.logger.info(f"Successfully processed PDF: {file_path}")
            return result
            
        except Exception as e:
            self.logger.error(f"Error processing PDF {file_path}: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'file_path': file_path,
                'processing_method': 'pdf_to_markdown'
            }
    
    def _extract_structured_markdown(self, file_path: str) -> str:
        """
        Extract structured markdown from PDF using pymupdf4llm.
        This preserves document structure, tables, and formatting.
        """
        try:
            # Use pymupdf4llm to convert PDF to markdown with structure preservation
            markdown_content = pymupdf4llm.to_markdown(
                file_path,
                page_chunks=False,  # Keep document as single chunk
                write_images=False,  # Don't extract images for now
                embed_images=False,
                show_progress=False
            )
            
            # Clean and enhance the markdown for better AI processing
            enhanced_markdown = self._enhance_markdown_structure(markdown_content)
            
            return enhanced_markdown
            
        except Exception as e:
            self.logger.error(f"Error extracting markdown from PDF: {str(e)}")
            raise
    
    def _enhance_markdown_structure(self, markdown_content: str) -> str:
        """
        Enhance markdown structure for better AI processing of NFe data.
        """
        # Add document type identifier
        enhanced = "# DOCUMENTO: NOTA FISCAL ELETRÔNICA (NFe)\n\n"
        enhanced += "## CONTEÚDO EXTRAÍDO DO PDF:\n\n"
        enhanced += markdown_content
        
        # Add processing instructions for AI
        enhanced += "\n\n## INSTRUÇÕES PARA EXTRAÇÃO:\n"
        enhanced += "Este documento deve ser processado para extrair todos os campos de uma NFe brasileira, "
        enhanced += "incluindo dados do emitente, destinatário, produtos/serviços, valores, impostos e informações fiscais.\n"
        
        return enhanced
    
    def _extract_pdf_metadata(self, file_path: str) -> Dict[str, Any]:
        """
        Extract basic metadata from PDF file.
        """
        try:
            doc = fitz.open(file_path)
            metadata = doc.metadata
            
            result = {
                'title': metadata.get('title', '') if metadata is not None else '',
                'author': metadata.get('author', '') if metadata is not None else '',
                'subject': metadata.get('subject', '') if metadata is not None else '',
                'creator': metadata.get('creator', '') if metadata is not None else '',
                'producer': metadata.get('producer', '') if metadata is not None else '',
                'created': metadata.get('creationDate', '') if metadata is not None else '',
                'modified': metadata.get('modDate', '') if metadata is not None else '',
                'pages': doc.page_count,
                'file_size': os.path.getsize(file_path) if os.path.exists(file_path) else 0
            }
            
            doc.close()
            return result
            
        except Exception as e:
            self.logger.error(f"Error extracting PDF metadata: {str(e)}")
            return {
                'pages': 0,
                'file_size': os.path.getsize(file_path) if os.path.exists(file_path) else 0,
                'error': str(e)
            }
    
    def validate_nfe_pdf(self, file_path: str) -> bool:
        """
        Basic validation to check if PDF might contain NFe data.
        """
        try:
            # Use pymupdf4llm to extract text for validation
            sample_text = pymupdf4llm.to_markdown(file_path, pages=[0])[:2000].upper()
            
            # Look for NFe indicators
            nfe_indicators = [
                'NOTA FISCAL ELETRÔNICA',
                'DANFE',
                'NFE',
                'CHAVE DE ACESSO',
                'CNPJ',
                'DESTINATÁRIO',
                'EMITENTE'
            ]
            
            found_indicators = sum(1 for indicator in nfe_indicators if indicator in sample_text)
            return found_indicators >= 3  # At least 3 indicators should be present
            
        except Exception as e:
            self.logger.error(f"Error validating NFe PDF: {str(e)}")
            return False