"""
Tax Table Extractor
Sistema especializado para extrair tabelas de impostos linha por linha
com máxima precisão na identificação de impostos brasileiros.
"""

import json
import logging
from typing import Dict, List, Any, Optional
from openai import OpenAI
import os

class TaxTableExtractor:
    """
    Extrator especializado de tabelas de impostos com abordagem linha por linha.
    """
    
    def __init__(self):
        self.client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
        self.logger = logging.getLogger(__name__)
    
    def extract_tax_table_lines(self, base64_image: str) -> List[Dict[str, Any]]:
        """
        Primeira etapa: Extrair cada linha da tabela de impostos individualmente.
        """
        try:
            prompt = """
            Você é um especialista em leitura de tabelas de impostos de NFe brasileiras.
            
            TAREFA: Extrair CADA LINHA da tabela de impostos, exatamente como aparece na imagem.
            
            FOQUE APENAS na seção "Impostos Federais/Estaduais" e "Impostos Municipais/Retidos".
            
            Para CADA linha de imposto que você encontrar, extraia:
            1. O NOME EXATO do imposto (como está escrito)
            2. O VALOR EXATO (em R$)
            3. A SEÇÃO onde está localizado (Federal/Estadual ou Municipal/Retido)
            
            EXEMPLO de como deve ser a resposta:
            {
                "linhas_impostos": [
                    {
                        "nome_imposto": "PIS:",
                        "valor": 47.82,
                        "secao": "Federal/Estadual"
                    },
                    {
                        "nome_imposto": "COFINS:",
                        "valor": 95.63,
                        "secao": "Federal/Estadual"
                    },
                    {
                        "nome_imposto": "INSS Retido:",
                        "valor": 31.88,
                        "secao": "Municipal/Retido"
                    }
                ]
            }
            
            IMPORTANTE:
            - Leia CADA linha individualmente
            - NÃO faça suposições sobre qual imposto deveria ter qual valor
            - Copie o nome EXATAMENTE como aparece
            - Identifique a seção correta baseada na localização visual
            """
            
            response = self.client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}}
                        ]
                    }
                ],
                max_tokens=1000,
                response_format={"type": "json_object"}
            )
            
            content = response.choices[0].message.content
            if content:
                result = json.loads(content)
                tax_lines = result.get('linhas_impostos', [])
            else:
                tax_lines = []
            
            self.logger.info(f"Extracted {len(tax_lines)} tax lines from image")
            for line in tax_lines:
                self.logger.info(f"  {line['nome_imposto']} = R$ {line['valor']} ({line['secao']})")
            
            return tax_lines
            
        except Exception as e:
            self.logger.error(f"Error extracting tax table lines: {str(e)}")
            return []
    
    def map_tax_lines_to_fields(self, tax_lines: List[Dict[str, Any]]) -> Dict[str, float]:
        """
        Segunda etapa: Mapear cada linha extraída para o campo correto do banco de dados.
        """
        # Dicionário de mapeamento baseado no nome do imposto
        tax_mapping = {
            # Impostos Federais/Estaduais
            'pis': ['PIS:', 'P.I.S.:', 'PIS', 'Contrib. PIS'],
            'cofins': ['COFINS:', 'C.O.F.I.N.S.:', 'COFINS', 'Contrib. COFINS'],
            'icms': ['ICMS:', 'I.C.M.S.:', 'ICMS'],
            'ipi': ['IPI:', 'I.P.I.:', 'IPI'],
            
            # Impostos Municipais/Retidos
            'ir': ['IR Retido:', 'I.R. Retido:', 'IRRF:', 'IR:', 'Imp. Renda Retido'],
            'inss': ['INSS Retido:', 'I.N.S.S. Retido:', 'INSS:', 'Contrib. Prev. Retida'],
            'csll': ['CSLL Retido:', 'C.S.L.L. Retido:', 'CSLL:', 'Contrib. Social Retida'],
            'issqn': ['ISSQN:', 'I.S.S.Q.N.:', 'ISS:', 'ISSQN'],
            'issrf': ['ISSRF (ISS Ret. Fonte):', 'ISS Ret. Fonte:', 'ISSRF:', 'ISS Retido Fonte'],
            'iss_retido': ['ISS Retido:', 'I.S.S. Retido:', 'ISS Ret.:']
        }
        
        mapped_values = {}
        
        for tax_line in tax_lines:
            nome_imposto = tax_line.get('nome_imposto', '').strip()
            valor = tax_line.get('valor', 0)
            secao = tax_line.get('secao', '')
            
            # Encontrar o campo correto baseado no nome
            campo_encontrado = None
            for campo, nomes_possiveis in tax_mapping.items():
                for nome_possivel in nomes_possiveis:
                    if nome_imposto.upper().startswith(nome_possivel.upper()):
                        campo_encontrado = campo
                        break
                if campo_encontrado:
                    break
            
            if campo_encontrado:
                # Validação adicional baseada na seção
                if campo_encontrado in ['pis', 'cofins', 'icms', 'ipi'] and 'Federal' not in secao:
                    self.logger.warning(f"Imposto federal '{nome_imposto}' encontrado fora da seção federal")
                
                if campo_encontrado in ['ir', 'inss', 'csll', 'issqn', 'issrf', 'iss_retido'] and 'Municipal' not in secao:
                    self.logger.warning(f"Imposto municipal '{nome_imposto}' encontrado fora da seção municipal")
                
                # Mapear para os nomes dos campos do banco
                field_mapping = {
                    'pis': 'valor_pis',
                    'cofins': 'valor_cofins',
                    'icms': 'valor_icms',
                    'ipi': 'valor_ipi',
                    'ir': 'valor_ir',
                    'inss': 'valor_inss',
                    'csll': 'valor_csll',
                    'issqn': 'valor_issqn',
                    'issrf': 'valor_issrf',
                    'iss_retido': 'valor_iss_retido'
                }
                
                field_name = field_mapping.get(campo_encontrado)
                if field_name:
                    mapped_values[field_name] = float(valor)
                    self.logger.info(f"Mapped '{nome_imposto}' (R$ {valor}) -> {field_name}")
                else:
                    self.logger.warning(f"No field mapping for tax type: {campo_encontrado}")
            else:
                self.logger.warning(f"Could not identify tax type for: {nome_imposto}")
        
        return mapped_values
    
    def extract_and_map_taxes(self, base64_image: str) -> Dict[str, float]:
        """
        Processo completo: extrair linhas e mapear para campos.
        """
        self.logger.info("Starting two-stage tax extraction process")
        
        # Etapa 1: Extrair linhas da tabela
        tax_lines = self.extract_tax_table_lines(base64_image)
        if not tax_lines:
            self.logger.error("No tax lines extracted from image")
            return {}
        
        # Etapa 2: Mapear para campos do banco
        mapped_taxes = self.map_tax_lines_to_fields(tax_lines)
        
        self.logger.info(f"Successfully mapped {len(mapped_taxes)} tax values")
        return mapped_taxes

def extract_taxes_with_precision(base64_image: str) -> Dict[str, float]:
    """
    Função principal para extrair impostos com máxima precisão.
    
    Args:
        base64_image: Imagem da NFe em base64
        
    Returns:
        Dicionário com os impostos mapeados corretamente
    """
    extractor = TaxTableExtractor()
    return extractor.extract_and_map_taxes(base64_image)