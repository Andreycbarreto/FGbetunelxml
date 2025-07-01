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

        ATENÇÃO ESPECIAL - CONFUSÃO COMUM IR vs INSS:
        - IR (Imposto de Renda): aparece como "IR", "I.R.", "IRRF", "IR RETIDO" 
        - INSS: aparece como "INSS", "I.N.S.S.", "INSS RETIDO"
        - São impostos DIFERENTES - não confunda!
        - IR é sobre renda, INSS é sobre previdência

        IMPOSTOS PARA PROCURAR (retorne 0.0 se não encontrar):
        - PIS: Procure EXATAMENTE por "PIS" na tabela
        - COFINS: Procure EXATAMENTE por "COFINS" na tabela
        - IR: Procure por "IR", "I.R.", "IRRF", "IR RETIDO" - NÃO confunda com INSS!
        - INSS: Procure por "INSS", "I.N.S.S.", "INSS RETIDO" - NÃO confunda com IR!
        - ISSQN: Procure por "ISSQN", "ISS", "ISS RETIDO"
        - CSLL: Procure por "CSLL", "C.S.L.L."

        REGRAS DE IDENTIFICAÇÃO:
        1. Se vir "IR" ou "I.R." = é IR (Imposto de Renda)
        2. Se vir "INSS" ou "I.N.S.S." = é INSS (Previdência)
        3. Nunca misture os dois - são completamente diferentes!

        RESPONDA EM JSON:
        {
            "valor_pis": 0.0,
            "valor_cofins": 0.0,
            "valor_ir": 0.0,
            "valor_inss": 0.0,
            "valor_issqn": 0.0,
            "valor_csll": 0.0,
            "found_values": ["lista dos impostos que você encontrou"],
            "identification_notes": "descreva brevemente o que você viu para IR e INSS"
        }

        IMPORTANTE: Leia com CUIDADO o nome de cada imposto. IR ≠ INSS!
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
                logger.info(f"IR vs INSS identification: {result.get('identification_notes', 'N/A')}")
                
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