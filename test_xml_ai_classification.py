#!/usr/bin/env python3
"""
Test XML AI classification
"""

import os
import logging
from xml_processor import NFEXMLProcessor

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_xml_ai_classification():
    """Test XML processing with AI classification"""
    
    test_files = [
        "./uploads/20250716_170804_35240460546801002556550020000405231131996745.xml",
        "./uploads/20250716_170804_35240460546801002556550020000405211287937474.xml",
        "./uploads/20250716_170804_35240460546801002556550020000405151122378439.xml"
    ]
    
    processor = NFEXMLProcessor()
    
    for test_file in test_files:
        if not os.path.exists(test_file):
            print(f"File not found: {test_file}")
            continue
            
        print(f"\n=== Testing: {os.path.basename(test_file)} ===")
        
        try:
            data = processor.process_xml_file(test_file)
            
            # Check operation type
            tipo_operacao = data.get('tipo_operacao', 'NOT_FOUND')
            print(f"AI Classification: {tipo_operacao}")
            
            # Check context used for classification
            numero_nf = data.get('numero_nf', 'NOT_FOUND')
            natureza_operacao = data.get('natureza_operacao', 'NOT_FOUND')
            
            print(f"Número NFe: {numero_nf}")
            print(f"Natureza operação: {natureza_operacao}")
            
            # Check items
            items = data.get('items', [])
            print(f"Items: {len(items)}")
            
            for i, item in enumerate(items[:2]):  # Show first 2 items
                produto = item.get('produto', 'N/A')
                descricao = item.get('descricao', 'N/A')
                cfop = item.get('cfop', 'N/A')
                print(f"  Item {i+1}: {produto} - {descricao} (CFOP: {cfop})")
            
            # Verify operation type is one of the expected values
            expected_values = ["Serviços e Produtos", "CT-e (Transporte)"]
            if tipo_operacao in expected_values:
                print("✅ AI classification is correct")
            else:
                print(f"❌ AI classification is incorrect: {tipo_operacao}")
                
        except Exception as e:
            print(f"❌ Error processing {test_file}: {e}")
            import traceback
            traceback.print_exc()
        
        print("-" * 50)

if __name__ == "__main__":
    test_xml_ai_classification()