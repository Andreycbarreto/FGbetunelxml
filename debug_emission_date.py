#!/usr/bin/env python3
"""
Debug script to diagnose emission date extraction issues
"""

import os
import sys
import logging
from datetime import datetime
from danfe_processor import DANFEProcessor, detect_if_danfe
from nfse_processor import NFSeProcessor, detect_if_nfse
from date_utils import extract_emission_date_from_text, validate_and_correct_date
import pymupdf as fitz

# Setup logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

def debug_emission_date_extraction(pdf_path: str):
    """Debug comprehensive emission date extraction from PDF"""
    
    print(f"\n=== DEBUGGING EMISSION DATE EXTRACTION ===")
    print(f"File: {pdf_path}")
    
    if not os.path.exists(pdf_path):
        print(f"ERROR: File not found: {pdf_path}")
        return
    
    # Step 1: Extract text from PDF
    print("\n1. EXTRACTING TEXT FROM PDF...")
    try:
        doc = fitz.open(pdf_path)
        text_content = ""
        for page in doc:
            text_content += page.get_text()
        doc.close()
        print(f"Text extracted successfully ({len(text_content)} characters)")
        
        # Show first 500 characters
        print("First 500 characters of text:")
        print(text_content[:500])
        print("...")
        
        # Look for date patterns in text
        print("\n2. SEARCHING FOR DATE PATTERNS IN TEXT...")
        emission_date_from_text = extract_emission_date_from_text(text_content)
        print(f"Emission date from text: {emission_date_from_text}")
        
        # Look for "emissão" keyword
        emission_lines = []
        for line in text_content.split('\n'):
            if 'emissão' in line.lower() or 'emissao' in line.lower():
                emission_lines.append(line.strip())
        
        print(f"Lines containing 'emissão': {len(emission_lines)}")
        for i, line in enumerate(emission_lines[:5]):  # Show first 5
            print(f"  {i+1}: {line}")
        
    except Exception as e:
        print(f"ERROR extracting text: {e}")
        return
    
    # Step 2: Detect document format
    print("\n3. DETECTING DOCUMENT FORMAT...")
    try:
        is_danfe = detect_if_danfe(pdf_path)
        is_nfse = detect_if_nfse(pdf_path)
        print(f"DANFE detected: {is_danfe}")
        print(f"NFS-e detected: {is_nfse}")
        
        processor = None
        if is_danfe:
            print("Using DANFE processor")
            processor = DANFEProcessor()
        elif is_nfse:
            print("Using NFS-e processor")
            processor = NFSeProcessor()
        else:
            print("No specialized processor detected")
            return
        
    except Exception as e:
        print(f"ERROR detecting format: {e}")
        return
    
    # Step 3: Process with specialized processor
    print("\n4. PROCESSING WITH SPECIALIZED PROCESSOR...")
    try:
        # Convert to images
        images = processor.convert_pdf_to_images(pdf_path)
        print(f"Converted to {len(images)} images")
        
        if not images:
            print("ERROR: No images generated")
            return
        
        # Extract data with GPT-4 Vision
        if is_danfe:
            raw_data = processor.extract_danfe_data_with_vision(images[0])
        else:
            raw_data = processor.extract_nfse_data_with_vision(images[0])
        
        print(f"Raw data extraction success: {bool(raw_data)}")
        
        if raw_data:
            print(f"Raw emission date: '{raw_data.get('data_emissao', 'NOT_FOUND')}'")
            
            # Step 4: Enhance date extraction
            print("\n5. ENHANCING DATE EXTRACTION...")
            enhanced_data = processor.enhance_date_extraction(raw_data, text_content)
            print(f"Enhanced emission date: '{enhanced_data.get('data_emissao', 'NOT_FOUND')}'")
            
            # Step 5: Normalize data
            print("\n6. NORMALIZING DATA...")
            if is_danfe:
                normalized_data = processor.normalize_danfe_data(enhanced_data)
            else:
                normalized_data = processor.normalize_nfse_data(enhanced_data)
            
            print(f"Final emission date: '{normalized_data.get('data_emissao', 'NOT_FOUND')}'")
            
            # Show all date-related fields
            print("\n7. ALL DATE-RELATED FIELDS:")
            for key, value in normalized_data.items():
                if 'data' in key.lower() or 'date' in key.lower():
                    print(f"  {key}: '{value}'")
        
    except Exception as e:
        print(f"ERROR during processing: {e}")
        import traceback
        traceback.print_exc()

def find_test_pdfs():
    """Find available test PDFs"""
    pdf_paths = []
    
    # Check uploads directory
    uploads_dir = "uploads"
    if os.path.exists(uploads_dir):
        for file in os.listdir(uploads_dir):
            if file.endswith('.pdf'):
                pdf_paths.append(os.path.join(uploads_dir, file))
    
    # Check attached_assets directory
    assets_dir = "attached_assets"
    if os.path.exists(assets_dir):
        for file in os.listdir(assets_dir):
            if file.endswith('.pdf'):
                pdf_paths.append(os.path.join(assets_dir, file))
    
    return pdf_paths

if __name__ == "__main__":
    print("=== EMISSION DATE EXTRACTION DEBUGGER ===")
    
    # Find test PDFs
    test_pdfs = find_test_pdfs()
    
    if not test_pdfs:
        print("No PDF files found for testing")
        print("Please ensure PDFs are available in uploads/ or attached_assets/ directories")
        sys.exit(1)
    
    print(f"Found {len(test_pdfs)} PDF files:")
    for i, pdf in enumerate(test_pdfs):
        print(f"  {i+1}: {pdf}")
    
    # Test each PDF
    for pdf_path in test_pdfs[:3]:  # Test first 3 PDFs
        try:
            debug_emission_date_extraction(pdf_path)
        except Exception as e:
            print(f"ERROR testing {pdf_path}: {e}")
        
        print("\n" + "="*60)