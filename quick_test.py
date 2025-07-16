#!/usr/bin/env python3
"""
Quick test to verify operation type classification
"""

import os
import base64
import pymupdf as fitz
from document_type_classifier import DocumentTypeClassifier

def quick_test():
    """Quick test of operation type classification"""
    
    test_file = "./attached_assets/3.3.2 NFe  CROSS DOCK_1751410903396.pdf"
    
    if not os.path.exists(test_file):
        print(f"Test file not found: {test_file}")
        return
    
    print(f"Testing: {test_file}")
    
    try:
        # Convert PDF to image
        doc = fitz.open(test_file)
        page = doc[0]
        pix = page.get_pixmap(matrix=fitz.Matrix(1, 1))  # Normal resolution
        img_data = pix.tobytes("png")
        base64_image = base64.b64encode(img_data).decode('utf-8')
        doc.close()
        
        # Test classification
        classifier = DocumentTypeClassifier()
        
        # First, test with extracted data context
        mock_data = {
            'items': [
                {
                    'codigo_servico': '16.02',
                    'descricao_servico': 'OUTRAS ATIVIDADES AUXILIARES DOS TRANSPORTES TERRESTRES'
                }
            ]
        }
        
        operation_type = classifier.classify_operation_type(base64_image, mock_data)
        print(f"Classification result: {operation_type}")
        
        # Verify it's one of the expected values
        expected_values = ["Serviços e Produtos", "CT-e (Transporte)"]
        if operation_type in expected_values:
            print("✓ Classification is valid")
        else:
            print(f"✗ Classification is invalid: {operation_type}")
            
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    quick_test()