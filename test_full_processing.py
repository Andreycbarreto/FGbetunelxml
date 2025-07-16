#!/usr/bin/env python3
"""
Test full processing pipeline with operation type classification
"""

import os
import logging
from pdf_vision_processor import PDFVisionProcessor
from document_type_classifier import DocumentTypeClassifier
from app import app, db
from models import UploadedFile, NFERecord, User, ProcessingStatus
from async_pdf_processor import AsyncPDFProcessor
from datetime import datetime

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_full_processing():
    """Test full processing pipeline"""
    
    test_files = [
        "./attached_assets/3.2.2 NFe TERMINAL PORTUARIO_1751410903396.pdf",
        "./attached_assets/3.3.2 NFe  CROSS DOCK_1751410903396.pdf"
    ]
    
    for test_file in test_files:
        if not os.path.exists(test_file):
            print(f"Test file not found: {test_file}")
            continue
            
        print(f"\n=== Testing: {os.path.basename(test_file)} ===")
        
        try:
            # Test just the vision processor
            processor = PDFVisionProcessor()
            result = processor.process_pdf_with_vision(test_file)
            
            print(f"Vision processor success: {result.get('success')}")
            print(f"Confidence: {result.get('confidence_score')}")
            
            if result.get('success'):
                data = result.get('data', {})
                
                # Check for tipo_operacao
                tipo_operacao = data.get('tipo_operacao', 'NOT_FOUND')
                print(f"Tipo operação: {tipo_operacao}")
                
                # Check for other key fields
                numero_nf = data.get('numero_nf', 'NOT_FOUND')
                emitente_nome = data.get('emitente_nome', 'NOT_FOUND')
                
                print(f"Número NFe: {numero_nf}")
                print(f"Emitente: {emitente_nome}")
                
                # Verify operation type is one of the expected values
                expected_values = ["Serviços e Produtos", "CT-e (Transporte)"]
                if tipo_operacao in expected_values:
                    print("✅ Operation type classification is correct")
                else:
                    print(f"❌ Operation type classification is incorrect: {tipo_operacao}")
            else:
                print(f"❌ Vision processing failed: {result.get('error')}")
                
        except Exception as e:
            print(f"❌ Error testing {test_file}: {e}")
            import traceback
            traceback.print_exc()

def test_classifier_alone():
    """Test classifier separately"""
    
    print("\n=== Testing Document Type Classifier Alone ===")
    
    test_file = "./attached_assets/3.2.2 NFe TERMINAL PORTUARIO_1751410903396.pdf"
    
    if not os.path.exists(test_file):
        print(f"Test file not found: {test_file}")
        return
        
    try:
        import pymupdf as fitz
        import base64
        
        # Convert PDF to image
        doc = fitz.open(test_file)
        page = doc[0]
        pix = page.get_pixmap(matrix=fitz.Matrix(1, 1))
        img_data = pix.tobytes("png")
        base64_image = base64.b64encode(img_data).decode('utf-8')
        doc.close()
        
        classifier = DocumentTypeClassifier()
        
        # Test with mock transport data
        transport_data = {
            'items': [
                {'descricao_servico': 'TERMINAL PORTUARIO'},
                {'codigo_servico': '16.01'}
            ]
        }
        
        result = classifier.classify_operation_type(base64_image, transport_data)
        print(f"Classification with transport data: {result}")
        
        # Test with mock service data
        service_data = {
            'items': [
                {'descricao_servico': 'CONSULTORIA EMPRESARIAL'},
                {'codigo_servico': '25.01'}
            ]
        }
        
        result = classifier.classify_operation_type(base64_image, service_data)
        print(f"Classification with service data: {result}")
        
    except Exception as e:
        print(f"❌ Error testing classifier: {e}")

if __name__ == "__main__":
    test_full_processing()
    test_classifier_alone()