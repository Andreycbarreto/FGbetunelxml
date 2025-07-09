#!/usr/bin/env python3
"""
Test the emission date extraction fix
"""

import os
import sys
import logging
from datetime import datetime
from danfe_processor import DANFEProcessor, detect_if_danfe
from nfse_processor import NFSeProcessor, detect_if_nfse
from emission_date_extractor import extract_emission_date_from_pdf
import pymupdf as fitz

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_emission_date_fix():
    """Test the emission date extraction fix"""
    
    print("=== TESTING EMISSION DATE EXTRACTION FIX ===")
    
    # Find test PDFs
    test_pdfs = []
    for root, dirs, files in os.walk("."):
        for file in files:
            if file.endswith('.pdf') and ('NFe' in file or 'NEW DEAL' in file):
                test_pdfs.append(os.path.join(root, file))
    
    if not test_pdfs:
        print("No test PDFs found")
        return
    
    print(f"Found {len(test_pdfs)} test PDFs")
    
    for pdf_path in test_pdfs[:3]:  # Test first 3
        print(f"\n--- Testing: {pdf_path} ---")
        
        # Test 1: Direct emission date extraction
        print("1. Testing direct emission date extraction...")
        emission_date = extract_emission_date_from_pdf(pdf_path)
        print(f"   Direct extraction result: {emission_date}")
        
        # Test 2: Format detection
        print("2. Testing format detection...")
        is_danfe = detect_if_danfe(pdf_path)
        is_nfse = detect_if_nfse(pdf_path)
        print(f"   DANFE: {is_danfe}, NFS-e: {is_nfse}")
        
        # Test 3: Full processing with specialized processor
        print("3. Testing full processing...")
        try:
            if is_danfe:
                processor = DANFEProcessor()
                result = processor.process_danfe_pdf(pdf_path, os.path.basename(pdf_path))
            elif is_nfse:
                processor = NFSeProcessor()
                result = processor.process_nfse_pdf(pdf_path, os.path.basename(pdf_path))
            else:
                print("   No specialized processor available")
                continue
            
            if result.get('success'):
                data = result.get('data', {})
                final_emission_date = data.get('data_emissao', 'NOT_FOUND')
                print(f"   Final emission date: {final_emission_date}")
                
                # Show some other extracted data for context
                other_fields = ['numero_nf', 'razao_social_emitente', 'valor_total_nf']
                for field in other_fields:
                    value = data.get(field, 'NOT_FOUND')
                    print(f"   {field}: {value}")
                
            else:
                print(f"   Processing failed: {result.get('error', 'Unknown error')}")
                
        except Exception as e:
            print(f"   Processing error: {e}")
        
        print("-" * 60)

if __name__ == "__main__":
    test_emission_date_fix()