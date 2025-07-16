#!/usr/bin/env python3
"""
Test operation type classification
"""

import os
import sys
import logging
from document_type_classifier import DocumentTypeClassifier
from pdf_vision_processor import PDFVisionProcessor

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_operation_classification():
    """Test the operation type classification"""
    
    print("=== TESTING OPERATION TYPE CLASSIFICATION ===")
    
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
    
    classifier = DocumentTypeClassifier()
    
    for pdf_path in test_pdfs[:3]:  # Test first 3
        print(f"\n--- Testing: {pdf_path} ---")
        
        try:
            # Convert PDF to image for classification
            import pymupdf as fitz
            import base64
            
            doc = fitz.open(pdf_path)
            page = doc[0]
            pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))  # 2x resolution
            img_data = pix.tobytes("png")
            base64_image = base64.b64encode(img_data).decode('utf-8')
            doc.close()
            
            # Test classification
            operation_type = classifier.classify_operation_type(base64_image)
            print(f"Classification: {operation_type}")
            
            # Also test with some mock extracted data for context
            mock_data = {
                'items': [
                    {'descricao_servico': 'SERVIÇOS OPERACIONAIS, VEÍCULOS A DISPOSIÇÃO'},
                    {'descricao_servico': 'LEVANTE DE CONTÊINER, UTILIZAÇÃO DE SCANNER'},
                ]
            }
            
            operation_type_with_data = classifier.classify_operation_type(base64_image, mock_data)
            print(f"Classification with context: {operation_type_with_data}")
            
        except Exception as e:
            print(f"Error testing {pdf_path}: {e}")
        
        print("-" * 50)

def test_with_vision_processor():
    """Test classification integrated with vision processor"""
    
    print("\n=== TESTING WITH VISION PROCESSOR ===")
    
    test_file = "./attached_assets/3.2.2 NFe TERMINAL PORTUARIO_1751410903396.pdf"
    
    if not os.path.exists(test_file):
        print(f"Test file not found: {test_file}")
        return
    
    print(f"Testing with: {test_file}")
    
    try:
        processor = PDFVisionProcessor()
        # This should be quick just to show the classification
        result = processor.process_pdf_with_vision(test_file)
        
        if result.get('success'):
            data = result.get('data', {})
            tipo_operacao = data.get('tipo_operacao', 'NOT_FOUND')
            print(f"Vision processor classification: {tipo_operacao}")
        else:
            print(f"Vision processor failed: {result.get('error')}")
            
    except Exception as e:
        print(f"Error with vision processor: {e}")

if __name__ == "__main__":
    test_operation_classification()
    test_with_vision_processor()