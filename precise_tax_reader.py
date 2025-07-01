"""
Precise Tax Reader
Simple and direct approach to read tax values accurately without inventing data.
Focus on reading ONLY what's visible in the document.
"""

import os
import json
import logging
from typing import Dict, Any, Optional
from openai import OpenAI

logger = logging.getLogger(__name__)

class PreciseTaxReader:
    """Simple, accurate tax reader that doesn't invent values"""
    
    def __init__(self):
        self.client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
        
    def read_taxes_only(self, base64_image: str) -> Dict[str, float]:
        """
        Read only tax values that are clearly visible in the document.
        Do NOT invent or calculate values.
        """
        
        prompt = """
        Você é um especialista em leitura de documentos fiscais brasileiros.

        INSTRUÇÕES CRÍTICAS:
        1. Leia APENAS os valores que estão CLARAMENTE VISÍVEIS no documento
        2. NÃO invente, calcule ou estime valores
        3. Se um valor não estiver visível, retorne 0.0
        4. Procure por uma tabela de impostos/tributos no documento
        5. Identifique cada linha da tabela com nome do imposto e valor

        IMPOSTOS PARA PROCURAR (retorne 0.0 se não encontrar):
        - PIS: Procure por "PIS" na tabela de impostos federais
        - COFINS: Procure por "COFINS" na tabela de impostos federais  
        - IR: Procure por "IR" ou "IRRF" na tabela de impostos retidos
        - INSS: Procure por "INSS" na tabela de impostos retidos
        - ISSQN: Procure por "ISSQN" ou "ISS" na tabela de impostos municipais
        - CSLL: Procure por "CSLL" na tabela de impostos

        RESPONDA EM JSON:
        {
            "valor_pis": 0.0,
            "valor_cofins": 0.0,
            "valor_ir": 0.0,
            "valor_inss": 0.0,
            "valor_issqn": 0.0,
            "valor_csll": 0.0,
            "found_values": ["lista dos impostos que você encontrou"]
        }

        IMPORTANTE: Apenas retorne valores que você pode VER claramente no documento.
        """
        
        try:
            response = self.client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {
                        "role": "user", 
                        "content": [
                            {"type": "text", "text": prompt},
                            {
                                "type": "image_url",
                                "image_url": {"url": f"data:image/png;base64,{base64_image}"}
                            }
                        ]
                    }
                ],
                max_tokens=500,
                response_format={"type": "json_object"}
            )
            
            content = response.choices[0].message.content
            if content:
                result = json.loads(content)
                logger.info(f"Found tax values: {result.get('found_values', [])}")
                
                # Extract only numeric values
                taxes = {
                    'valor_pis': float(result.get('valor_pis', 0.0)),
                    'valor_cofins': float(result.get('valor_cofins', 0.0)),
                    'valor_ir': float(result.get('valor_ir', 0.0)),
                    'valor_inss': float(result.get('valor_inss', 0.0)),
                    'valor_issqn': float(result.get('valor_issqn', 0.0)),
                    'valor_csll': float(result.get('valor_csll', 0.0))
                }
                
                logger.info(f"Precise tax reading results: {taxes}")
                return taxes
            else:
                logger.warning("No content returned from tax reading")
                return self._zero_taxes()
                
        except Exception as e:
            logger.error(f"Error in precise tax reading: {str(e)}")
            return self._zero_taxes()
    
    def _zero_taxes(self) -> Dict[str, float]:
        """Return zero values for all taxes"""
        return {
            'valor_pis': 0.0,
            'valor_cofins': 0.0,
            'valor_ir': 0.0,
            'valor_inss': 0.0,
            'valor_issqn': 0.0,
            'valor_csll': 0.0
        }

def read_taxes_precisely(base64_image: str) -> Dict[str, float]:
    """
    Read tax values precisely from document image.
    
    Args:
        base64_image: Base64 encoded image of the document
        
    Returns:
        Dictionary with precise tax values (no invented data)
    """
    reader = PreciseTaxReader()
    return reader.read_taxes_only(base64_image)