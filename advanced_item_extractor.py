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
        Analise esta nota fiscal brasileira e extraia TODOS os campos detalhados dos ITENS/SERVIÇOS.

        🔍 INSTRUÇÕES DE BUSCA - EXAMINE ESTAS SEÇÕES:

        1️⃣ TABELA PRINCIPAL DE ITENS:
        - Coluna "CÓDIGOS": onde estão "Serviço:" e "Atividade:"
        - Coluna "PRODUTO/SERVIÇO": descrição completa
        - Colunas de valores e quantidades

        2️⃣ SEÇÃO DETALHADA "DESCRIÇÃO DOS SERVIÇOS PRESTADOS":
        - Código do serviço (ex: 3301)
        - Local de prestação (ex: 7435)
        - Alíquota (ex: 2%)
        - Valor do serviço
        - Detalhamento de impostos (IR, INSS, CSLL, COFINS, PIS)
        - Valor ISS, Base de cálculo, etc.

        🎯 CAMPOS OBRIGATÓRIOS A EXTRAIR:

        ✅ CÓDIGOS BÁSICOS:
        - codigo_servico: formato XX.XX (busque "Serviço: XXXX" e formate como XX.XX)
        - codigo_atividade: números longos (busque "Atividade: XXXXXXX")
        - descricao_servico: texto completo da descrição

        ✅ DETALHES DO SERVIÇO (da seção detalhada):
        - servico_codigo: código numérico (ex: 3301)
        - servico_local_prestacao: código local (ex: 7435) 
        - servico_aliquota: percentual (ex: 2.0)
        - servico_valor: valor total do serviço
        - servico_natureza_operacao: texto da natureza
        - servico_discriminacao: discriminação detalhada

        ✅ IMPOSTOS DETALHADOS:
        - tax_ir: valor IR
        - tax_inss: valor INSS
        - tax_csll: valor CSLL
        - tax_cofins: valor COFINS
        - tax_pis: valor PIS
        - tax_issqn: valor ISSQN/ISS
        - tax_base_calculo: base de cálculo
        - tax_valor_liquido: valor líquido final

        ✅ VALORES COMERCIAIS:
        - quantidade_comercial, valor_unitario_comercial, valor_total_produto, unidade_comercial

        📋 REGRAS DE FORMATAÇÃO:
        - Código serviço: se encontrar "3301", formate como "33.01"
        - Valores: sempre números decimais
        - Textos: manter formatação original

        JSON RESULTADO COMPLETO:
        {
            "items": [
                {
                    "codigo_servico": "33.01",
                    "codigo_atividade": "77400000",
                    "descricao_servico": "Serviços de desembaraço aduaneiro, comissários, despachantes e congêneres",
                    "servico_codigo": "3301",
                    "servico_local_prestacao": "7435",
                    "servico_aliquota": 2.0,
                    "servico_valor": 3187.80,
                    "servico_natureza_operacao": "Exigível",
                    "servico_discriminacao": "DIMDOC/0425...",
                    "tax_ir": 47.82,
                    "tax_inss": 0.0,
                    "tax_csll": 31.88,
                    "tax_cofins": 95.63,
                    "tax_pis": 20.72,
                    "tax_issqn": 63.76,
                    "tax_base_calculo": 3187.80,
                    "tax_valor_liquido": 2991.75,
                    "quantidade_comercial": 1.0,
                    "valor_unitario_comercial": 3187.80,
                    "valor_total_produto": 3187.80,
                    "unidade_comercial": "UN"
                }
            ]
        }

        PROCURE EM TODAS AS SEÇÕES DO DOCUMENTO - TABELA E DETALHAMENTO!
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
                # Basic service fields
                'codigo_servico': self._clean_service_code(raw_item.get('codigo_servico')),
                'codigo_atividade': self._clean_activity_code(raw_item.get('codigo_atividade')),
                'descricao_servico': self._clean_description(raw_item.get('descricao_servico')),
                
                # Detailed service fields
                'servico_codigo': self._clean_string(raw_item.get('servico_codigo'), 10),
                'servico_local_prestacao': self._clean_string(raw_item.get('servico_local_prestacao'), 10),
                'servico_aliquota': self._parse_decimal(raw_item.get('servico_aliquota')),
                'servico_valor': self._parse_decimal(raw_item.get('servico_valor')),
                'servico_natureza_operacao': self._clean_string(raw_item.get('servico_natureza_operacao'), 255),
                'servico_discriminacao': self._clean_description(raw_item.get('servico_discriminacao')),
                'servico_descricao_incondicional': self._parse_decimal(raw_item.get('servico_descricao_incondicional')),
                'servico_valor_deducao': self._parse_decimal(raw_item.get('servico_valor_deducao')),
                'servico_valor_iss': self._parse_decimal(raw_item.get('servico_valor_iss')),
                
                # Tax fields
                'tax_ir': self._parse_decimal(raw_item.get('tax_ir')),
                'tax_inss': self._parse_decimal(raw_item.get('tax_inss')),
                'tax_csll': self._parse_decimal(raw_item.get('tax_csll')),
                'tax_cofins': self._parse_decimal(raw_item.get('tax_cofins')),
                'tax_pis': self._parse_decimal(raw_item.get('tax_pis')),
                'tax_issqn': self._parse_decimal(raw_item.get('tax_issqn')),
                'tax_base_calculo': self._parse_decimal(raw_item.get('tax_base_calculo')),
                'tax_valor_liquido': self._parse_decimal(raw_item.get('tax_valor_liquido')),
                'tax_outras_retencoes': self._parse_decimal(raw_item.get('tax_outras_retencoes')),
                'tax_total_tributos_federais': self._parse_decimal(raw_item.get('tax_total_tributos_federais')),
                'tax_descricao_condicional': self._parse_decimal(raw_item.get('tax_descricao_condicional')),
                
                # Commercial fields
                'quantidade_comercial': self._parse_decimal(raw_item.get('quantidade_comercial', raw_item.get('quantidade', 1.0))),
                'valor_unitario_comercial': self._parse_decimal(raw_item.get('valor_unitario_comercial', raw_item.get('valor_unitario', 0.0))),
                'valor_total_produto': self._parse_decimal(raw_item.get('valor_total_produto', raw_item.get('valor_total', 0.0))),
                'unidade_comercial': self._clean_string(raw_item.get('unidade_comercial', raw_item.get('unidade', 'UN')), 10)
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
        if code is None or code == 'null' or code == '':
            logger.warning("Service code is None/null - AI might not have found it in the document")
            return ''
        
        code_str = str(code).strip()
        # Remove caracteres extras, manter apenas números e ponto
        import re
        cleaned = re.sub(r'[^\d.]', '', code_str)
        
        # Se já tem formato XX.XX, validar
        if '.' in cleaned and len(cleaned.split('.')) == 2:
            parts = cleaned.split('.')
            if len(parts[0]) in [1, 2] and len(parts[1]) in [1, 2]:
                logger.info(f"Valid service code found: {cleaned}")
                return cleaned[:20]
        
        # Se é um número de 4 dígitos (ex: 3301), formatar como XX.XX
        elif cleaned and cleaned.isdigit() and len(cleaned) == 4:
            formatted = f"{cleaned[:2]}.{cleaned[2:]}"
            logger.info(f"Formatted service code: {cleaned} -> {formatted}")
            return formatted
        
        # Se é um número de 3 dígitos (ex: 301), formatar como X.XX
        elif cleaned and cleaned.isdigit() and len(cleaned) == 3:
            formatted = f"{cleaned[:1]}.{cleaned[1:]}"
            logger.info(f"Formatted service code: {cleaned} -> {formatted}")
            return formatted
        
        logger.warning(f"Invalid service code format: {code_str} -> {cleaned}")
        return cleaned[:20] if cleaned else ''
    
    def _clean_activity_code(self, code) -> str:
        """Clean activity code (CNAE)"""
        if code is None or code == 'null' or code == '':
            logger.warning("Activity code is None/null - AI might not have found it in the document")
            return ''
        
        code_str = str(code).strip()
        # Remove caracteres não numéricos
        import re
        cleaned = re.sub(r'[^\d]', '', code_str)
        
        # Validar se é um CNAE válido (geralmente 7 dígitos)
        if cleaned and len(cleaned) >= 6 and len(cleaned) <= 8:
            logger.info(f"Valid activity code found: {cleaned}")
            return cleaned[:20]
        elif cleaned:
            logger.warning(f"Activity code found but unusual format: {code_str} -> {cleaned}")
            return cleaned[:20]
        
        logger.warning(f"No valid activity code found: {code_str}")
        return ''
    
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