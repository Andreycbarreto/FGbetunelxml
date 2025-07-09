#!/usr/bin/env python3
"""
Test complete integration of emission date extraction
"""

import os
import sys
import logging
from pdf_vision_processor import PDFVisionProcessor
from async_pdf_processor import AsyncPDFProcessor

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_complete_integration():
    """Test complete integration with PDF vision processor"""
    
    print("=== TESTING COMPLETE INTEGRATION ===")
    
    test_file = "./attached_assets/NF NEW DEAL 11220_1751410916288.pdf"
    
    if not os.path.exists(test_file):
        print(f"Test file not found: {test_file}")
        return
    
    print(f"Testing with: {test_file}")
    
    # Test direct vision processing
    print("\n1. Testing direct vision processing...")
    
    try:
        processor = PDFVisionProcessor()
        result = processor.process_pdf_with_vision(test_file)
        
        if result.get('success'):
            data = result.get('data', {})
            emission_date = data.get('data_emissao', 'NOT_FOUND')
            print(f"✓ Vision processing successful")
            print(f"✓ Emission date: {emission_date}")
            print(f"✓ Processing method: {result.get('processing_method')}")
            
            # Show other key fields
            key_fields = ['numero_nf', 'razao_social_emitente', 'cnpj_emitente', 'valor_total_nf']
            for field in key_fields:
                value = data.get(field, 'NOT_FOUND')
                print(f"  {field}: {value}")
                
        else:
            print(f"✗ Vision processing failed: {result.get('error')}")
            
    except Exception as e:
        print(f"✗ Vision processing error: {e}")

if __name__ == "__main__":
    test_complete_integration()