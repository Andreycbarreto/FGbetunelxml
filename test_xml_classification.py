#!/usr/bin/env python3
"""
Test XML processing with operation type classification
"""

import os
import logging
from xml_processor import NFEXMLProcessor

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_xml_classification():
    """Test XML processing with operation type classification"""
    
    # Find XML files
    xml_files = []
    for root, dirs, files in os.walk("."):
        for file in files:
            if file.endswith('.xml'):
                xml_files.append(os.path.join(root, file))
    
    if not xml_files:
        print("No XML files found")
        return
    
    print(f"Found {len(xml_files)} XML files")
    
    processor = NFEXMLProcessor()
    
    for xml_file in xml_files[:3]:  # Test first 3
        print(f"\n--- Testing: {xml_file} ---")
        
        try:
            data = processor.process_xml_file(xml_file)
            
            # Check operation type
            tipo_operacao = data.get('tipo_operacao', 'NOT_FOUND')
            print(f"Tipo operação: {tipo_operacao}")
            
            # Check other key fields
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
                print("✅ Operation type classification is correct")
            else:
                print(f"❌ Operation type classification is incorrect: {tipo_operacao}")
                
        except Exception as e:
            print(f"❌ Error processing {xml_file}: {e}")
            import traceback
            traceback.print_exc()
        
        print("-" * 50)

if __name__ == "__main__":
    test_xml_classification()