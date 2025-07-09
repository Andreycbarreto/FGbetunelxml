#!/usr/bin/env python3
"""
Test a single PDF for emission date extraction
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
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_pdf_with_vision_only(pdf_path: str):
    """Test PDF with vision processing only"""
    print(f"\n=== TESTING PDF WITH VISION ONLY ===")
    print(f"File: {pdf_path}")
    
    try:
        # Test DANFE processor
        processor = DANFEProcessor()
        
        # Convert to images
        images = processor.convert_pdf_to_images(pdf_path)
        print(f"Generated {len(images)} images")
        
        if images:
            # Extract with vision
            raw_data = processor.extract_danfe_data_with_vision(images[0])
            print(f"Raw data keys: {list(raw_data.keys()) if raw_data else 'No data'}")
            
            if raw_data:
                emission_date = raw_data.get('data_emissao', 'NOT_FOUND')
                print(f"RAW EMISSION DATE: '{emission_date}'")
                
                # Test fallback methods
                if not emission_date or emission_date == '':
                    print("Testing fallback methods...")
                    
                    # Extract text from PDF
                    doc = fitz.open(pdf_path)
                    text_content = ""
                    for page in doc:
                        text_content += page.get_text()
                    doc.close()
                    
                    # Try text extraction
                    text_date = extract_emission_date_from_text(text_content)
                    print(f"Text extraction date: '{text_date}'")
                    
                    # Enhanced data processing
                    enhanced_data = processor.enhance_date_extraction(raw_data, text_content)
                    print(f"Enhanced emission date: '{enhanced_data.get('data_emissao', 'NOT_FOUND')}'")
                    
                    # Show some text for manual inspection
                    print("\nFirst 1000 chars of text:")
                    print(text_content[:1000])
                    
                    # Look for emission patterns
                    lines_with_emissao = []
                    for line in text_content.split('\n'):
                        if 'emissão' in line.lower() or 'emissao' in line.lower():
                            lines_with_emissao.append(line.strip())
                    
                    print(f"\nLines with 'emissão': {len(lines_with_emissao)}")
                    for line in lines_with_emissao[:10]:
                        print(f"  → {line}")
                    
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    # Test with a specific PDF
    test_pdf = "attached_assets/NF NEW DEAL 11220_1751410916288.pdf"
    
    if os.path.exists(test_pdf):
        test_pdf_with_vision_only(test_pdf)
    else:
        print(f"Test PDF not found: {test_pdf}")
        
        # List available PDFs
        print("\nAvailable PDFs:")
        for root, dirs, files in os.walk("attached_assets"):
            for file in files:
                if file.endswith('.pdf'):
                    print(f"  - {os.path.join(root, file)}")