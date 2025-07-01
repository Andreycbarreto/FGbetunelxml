"""
Advanced Item Field Extractor
Specialized system for precise extraction of service-related item fields
"""

import os
import json
import logging
from typing import Dict, Any, List
from openai import OpenAI

logger = logging.getLogger(__name__)

class AdvancedItemExtractor:
    """Advanced extractor for service item fields with field separation"""
    
    def __init__(self):
        self.client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
    
    def extract_item_fields_precisely(self, base64_image: str) -> List[Dict[str, Any]]:
        """
        Extract item fields with precise separation of service codes and descriptions
        
        Args:
            base64_image: Base64 encoded image of the document
            
        Returns:
            List of items with properly separated fields
        """
        
        prompt = """
        Analise esta nota fiscal brasileira e extraia os campos dos ITENS com máxima precisão.

        FOQUE na seção de ITENS/PRODUTOS/SERVIÇOS e extraia para cada item:

        CAMPOS OBRIGATÓRIOS:
        1. CÓDIGO DO SERVIÇO: Código numérico do serviço (ex: 14.07, 25.05, 1.05)
           - Procure por "Cód. Serv.", "Código Serviço", números com ponto (XX.XX)
           - DIFERENTE do código do produto/item

        2. CÓDIGO DA ATIVIDADE: Código da atividade econômica (CNAE)
           - Procure por "Cód. Ativ.", "Código Atividade", "CNAE"
           - Geralmente um número maior (ex: 6201500, 7319004)

        3. DESCRIÇÃO DO SERVIÇO: Descrição completa do serviço prestado
           - O texto que descreve o que foi feito/vendido
           - Pode ser longo e detalhado

        4. OUTROS CAMPOS PADRÃO:
           - Quantidade
           - Valor unitário  
           - Valor total
           - Unidade de medida

        INSTRUÇÕES ESPECÍFICAS:
        - Se não encontrar um campo específico, retorne null
        - NÃO invente códigos ou descrições
        - Mantenha a descrição original completa
        - Códigos de serviço são diferentes de códigos de produto

        RETORNE EM JSON:
        {
            "items": [
                {
                    "codigo_servico": "14.07",
                    "codigo_atividade": "6201500", 
                    "descricao_servico": "Desenvolvimento de software sob encomenda",
                    "quantidade": 1.0,
                    "valor_unitario": 1000.00,
                    "valor_total": 1000.00,
                    "unidade": "UN"
                }
            ]
        }
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
                max_tokens=1000,
                response_format={"type": "json_object"}
            )
            
            content = response.choices[0].message.content
            if content:
                result = json.loads(content)
                items = result.get('items', [])
                
                # Validar e limpar os dados
                cleaned_items = []
                for item in items:
                    cleaned_item = self._clean_item_data(item)
                    if cleaned_item:
                        cleaned_items.append(cleaned_item)
                
                logger.info(f"Extracted {len(cleaned_items)} items with service fields")
                return cleaned_items
            else:
                return []
                
        except Exception as e:
            logger.error(f"Error in advanced item extraction: {str(e)}")
            return []
    
    def _clean_item_data(self, raw_item: Dict) -> Dict[str, Any]:
        """Clean and validate item data"""
        
        try:
            cleaned = {
                'codigo_servico': self._clean_service_code(raw_item.get('codigo_servico')),
                'codigo_atividade': self._clean_activity_code(raw_item.get('codigo_atividade')),
                'descricao_servico': self._clean_description(raw_item.get('descricao_servico')),
                'quantidade': self._parse_decimal(raw_item.get('quantidade', 1.0)),
                'valor_unitario': self._parse_decimal(raw_item.get('valor_unitario', 0.0)),
                'valor_total': self._parse_decimal(raw_item.get('valor_total', 0.0)),
                'unidade': self._clean_string(raw_item.get('unidade', 'UN'), 10)
            }
            
            # Pelo menos descrição deve existir
            if not cleaned['descricao_servico']:
                return None
                
            return cleaned
            
        except Exception as e:
            logger.error(f"Error cleaning item data: {str(e)}")
            return None
    
    def _clean_service_code(self, code) -> str:
        """Clean service code (format: XX.XX)"""
        if not code or code == 'null':
            return ''
        
        code_str = str(code).strip()
        # Remove caracteres extras, manter apenas números e ponto
        import re
        cleaned = re.sub(r'[^\d.]', '', code_str)
        
        # Limitar tamanho
        return cleaned[:20] if cleaned else ''
    
    def _clean_activity_code(self, code) -> str:
        """Clean activity code (CNAE)"""
        if not code or code == 'null':
            return ''
        
        code_str = str(code).strip()
        # Remove caracteres não numéricos
        import re
        cleaned = re.sub(r'[^\d]', '', code_str)
        
        # Limitar tamanho
        return cleaned[:20] if cleaned else ''
    
    def _clean_description(self, desc) -> str:
        """Clean service description"""
        if not desc or desc == 'null':
            return ''
        
        desc_str = str(desc).strip()
        # Limitar tamanho para evitar truncamento no banco
        return desc_str[:500] if desc_str else ''
    
    def _clean_string(self, value, max_length=255) -> str:
        """Clean string field with length limit"""
        if not value or value == 'null':
            return ''
        
        return str(value).strip()[:max_length]
    
    def _parse_decimal(self, value) -> float:
        """Parse decimal value"""
        if value is None or value == 'null':
            return 0.0
        try:
            return float(value)
        except (ValueError, TypeError):
            return 0.0

def extract_advanced_item_fields(base64_image: str) -> List[Dict[str, Any]]:
    """
    Extract item fields with advanced service field separation
    
    Args:
        base64_image: Base64 encoded image of the document
        
    Returns:
        List of items with separated service fields
    """
    extractor = AdvancedItemExtractor()
    return extractor.extract_item_fields_precisely(base64_image)