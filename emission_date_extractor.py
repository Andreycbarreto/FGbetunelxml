#!/usr/bin/env python3
"""
Specialized emission date extractor with simple, focused prompts
"""

import os
import base64
import logging
from typing import Dict, Any, Optional
from openai import OpenAI
import pymupdf as fitz
import json
from json_cleaner import clean_and_parse_json

class EmissionDateExtractor:
    """Specialized extractor focused only on emission dates"""
    
    def __init__(self):
        self.client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
        self.logger = logging.getLogger(__name__)
        
    def extract_emission_date_only(self, base64_image: str) -> Optional[str]:
        """Extract ONLY emission date from document image"""
        
        simple_prompt = """
Você é um especialista em documentos fiscais brasileiros. 

TAREFA SIMPLES: Encontre APENAS a data de emissão neste documento.

PROCURE POR:
- "Data de Emissão"
- "DT. EMISSÃO" 
- "EMISSÃO"
- "Data Emissão"
- "Dt. Emissão"

FORMATO ESPERADO: dd/mm/yyyy (exemplo: 15/03/2024)

INSTRUÇÕES:
1. Olhe no cabeçalho do documento
2. Encontre a data ao lado de "Data de Emissão" ou similar
3. Leia EXATAMENTE o que está escrito
4. Responda APENAS com a data no formato dd/mm/yyyy
5. Se não encontrar, responda "NÃO_ENCONTRADO"

EXEMPLO DE RESPOSTA:
15/03/2024
"""
        
        try:
            response = self.client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": simple_prompt},
                            {
                                "type": "image_url",
                                "image_url": {"url": f"data:image/png;base64,{base64_image}"}
                            }
                        ]
                    }
                ],
                max_tokens=100,
                temperature=0
            )
            
            result = response.choices[0].message.content.strip()
            self.logger.info(f"Emission date extraction result: '{result}'")
            
            # Clean the result
            if result and result != "NÃO_ENCONTRADO":
                # Remove any extra text and extract just the date
                import re
                date_pattern = r'\d{1,2}[/.-]\d{1,2}[/.-]\d{4}'
                match = re.search(date_pattern, result)
                if match:
                    return match.group(0).replace('-', '/').replace('.', '/')
            
            return None
            
        except Exception as e:
            self.logger.error(f"Error extracting emission date: {e}")
            return None

def extract_emission_date_from_pdf(pdf_path: str) -> Optional[str]:
    """
    Extract emission date from PDF using specialized extractor
    
    Args:
        pdf_path: Path to PDF file
        
    Returns:
        Emission date in dd/mm/yyyy format or None
    """
    
    extractor = EmissionDateExtractor()
    
    try:
        # Convert PDF to image
        doc = fitz.open(pdf_path)
        page = doc[0]  # First page only
        
        # High resolution for better OCR
        mat = fitz.Matrix(2.0, 2.0)
        pix = page.get_pixmap(matrix=mat)
        img_data = pix.tobytes("png")
        base64_img = base64.b64encode(img_data).decode('utf-8')
        
        doc.close()
        
        # Extract emission date
        emission_date = extractor.extract_emission_date_only(base64_img)
        
        return emission_date
        
    except Exception as e:
        logging.error(f"Error processing PDF {pdf_path}: {e}")
        return None

if __name__ == "__main__":
    # Test with sample PDF
    test_pdf = "attached_assets/NF NEW DEAL 11220_1751410916288.pdf"
    
    if os.path.exists(test_pdf):
        print(f"Testing emission date extraction from: {test_pdf}")
        emission_date = extract_emission_date_from_pdf(test_pdf)
        print(f"Extracted emission date: {emission_date}")
    else:
        print(f"Test PDF not found: {test_pdf}")