#!/usr/bin/env python3
"""
Script to test PDF processing and debug extraction issues
"""
import os
import sys
import logging
from universal_pdf_simple import process_pdf_universal_simple

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(name)s:%(levelname)s:%(message)s')

def test_pdf_processing():
    """Test PDF processing with detailed logging"""
    pdf_path = "uploads/test_terminal.pdf"
    
    if not os.path.exists(pdf_path):
        print(f"Error: PDF file not found at {pdf_path}")
        return
    
    print(f"Testing PDF processing for: {pdf_path}")
    print("-" * 50)
    
    try:
        result = process_pdf_universal_simple(pdf_path)
        
        print("Processing result:")
        print(f"Success: {result.get('success', False)}")
        print(f"Confidence: {result.get('confidence_score', 0)}")
        print(f"Error: {result.get('error', 'None')}")
        
        data = result.get('data', {})
        print(f"\nData keys found: {list(data.keys())}")
        
        # Check main document fields
        main_fields = [
            'numero_nf', 'serie', 'razao_social_emitente', 'cnpj_emitente', 
            'razao_social_destinatario', 'cnpj_destinatario', 'valor_total_nota'
        ]
        
        print(f"\nMain document fields:")
        for field in main_fields:
            value = data.get(field, 'NOT_FOUND')
            print(f"  {field}: {value}")
        
        # Check items
        items = data.get('items', [])
        print(f"\nItems found: {len(items)}")
        for i, item in enumerate(items[:3]):  # Show first 3 items
            print(f"  Item {i+1}: {item.get('descricao', 'No description')}")
        
    except Exception as e:
        print(f"Error during processing: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_pdf_processing()