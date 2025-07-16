#!/usr/bin/env python3
"""
Test PDF processing to verify operation type classification
"""

import os
import logging
from pdf_vision_processor import PDFVisionProcessor

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_pdf_processing():
    """Test PDF processing with operation type classification"""
    
    test_file = "./attached_assets/3.3.2 NFe  CROSS DOCK_1751410903396.pdf"
    
    if not os.path.exists(test_file):
        print(f"Test file not found: {test_file}")
        return
    
    print(f"Testing PDF: {test_file}")
    
    try:
        processor = PDFVisionProcessor()
        result = processor.process_pdf_with_vision(test_file)
        
        print(f"\nResult success: {result.get('success')}")
        print(f"Confidence: {result.get('confidence_score')}")
        
        if result.get('success'):
            data = result.get('data', {})
            print(f"\nExtracted data keys: {list(data.keys())}")
            
            # Check specifically for tipo_operacao
            tipo_operacao = data.get('tipo_operacao', 'NOT_FOUND')
            print(f"tipo_operacao: {tipo_operacao}")
            
            # Check for other key fields
            numero_nf = data.get('numero_nf', 'NOT_FOUND')
            emitente_nome = data.get('emitente_nome', 'NOT_FOUND')
            
            print(f"numero_nf: {numero_nf}")
            print(f"emitente_nome: {emitente_nome}")
            
        else:
            print(f"Processing failed: {result.get('error')}")
            
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_pdf_processing()