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
        
        # Validate base64 image
        if not base64_image or len(base64_image) < 100:
            logger.warning("Invalid or empty base64 image provided")
            return []
        
        prompt = """
        Analise esta nota fiscal brasileira e extraia TODOS os itens com MÁXIMA PRECISÃO nos campos de serviço.

        PROCURE na tabela/seção de ITENS por estas informações ESPECÍFICAS:

        🔍 CÓDIGO DO SERVIÇO (formato: XX.XX):
        - Procure números como: 14.07, 25.05, 1.05, 17.06, etc.
        - Pode estar em colunas: "Cód.Serv.", "Código Serviço", "LC 116"
        - É diferente do código do produto/NCM

        🔍 CÓDIGO DA ATIVIDADE (CNAE - números longos):
        - Procure números como: 6201500, 7319004, 6202300, etc.
        - Pode estar em: "Cód.Ativ.", "Código Atividade", "CNAE"
        - Geralmente 7 dígitos

        🔍 DESCRIÇÃO DO SERVIÇO:
        - Texto completo que descreve o serviço
        - Exemplos: "Desenvolvimento de software", "Consultoria em TI", etc.
        - Pode ser longo - mantenha completo

        🔍 OUTROS DADOS:
        - Quantidade (normalmente 1 para serviços)
        - Valor unitário
        - Valor total
        - Unidade (UN, HR, etc.)

        ⚠️ REGRAS CRÍTICAS:
        - Se um campo não existir na nota, coloque null
        - NÃO invente códigos - apenas o que está escrito
        - Analise cada linha da tabela de itens
        - Códigos de serviço SÃO DIFERENTES de códigos NCM/produto

        FORMATO DE SAÍDA JSON:
        {
            "items": [
                {
                    "codigo_servico": "14.07",
                    "codigo_atividade": "6201500",
                    "descricao_servico": "Desenvolvimento de aplicações e websites sob encomenda",
                    "quantidade": 1.0,
                    "valor_unitario": 3187.50,
                    "valor_total": 3187.50,
                    "unidade": "UN"
                }
            ]
        }

        Procure com atenção na tabela visual da nota fiscal!
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
                for i, item in enumerate(items):
                    logger.info(f"Raw item {i+1}: {item}")
                    cleaned_item = self._clean_item_data(item)
                    if cleaned_item:
                        logger.info(f"Cleaned item {i+1}: {cleaned_item}")
                        cleaned_items.append(cleaned_item)
                    else:
                        logger.warning(f"Item {i+1} was filtered out during cleaning")
                
                logger.info(f"Final result: {len(cleaned_items)} items extracted")
                for i, item in enumerate(cleaned_items):
                    logger.info(f"Item {i+1} - Service Code: '{item.get('codigo_servico', 'N/A')}', Activity Code: '{item.get('codigo_atividade', 'N/A')}', Description: '{item.get('descricao_servico', 'N/A')[:50]}...'")
                
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
                'quantidade_comercial': self._parse_decimal(raw_item.get('quantidade', 1.0)),
                'valor_unitario_comercial': self._parse_decimal(raw_item.get('valor_unitario', 0.0)),
                'valor_total_produto': self._parse_decimal(raw_item.get('valor_total', 0.0)),
                'unidade_comercial': self._clean_string(raw_item.get('unidade', 'UN'), 10)
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