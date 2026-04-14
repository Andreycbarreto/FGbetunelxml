"""
DANFE Specialized Processor
Processador especializado para documentos DANFE (Documento Auxiliar da Nota Fiscal Eletrônica)
com reconhecimento específico dos padrões de layout brasileiro
"""
import os
import logging
import json
import base64
from typing import Dict, Any, List, Optional
from openai import OpenAI
import pymupdf as fitz  # PyMuPDF
from date_utils import clean_date_fields, validate_and_correct_date, extract_emission_date_from_text
from json_cleaner import clean_and_parse_json

class DANFEProcessor:
    """Processador especializado para documentos DANFE"""
    
    def __init__(self):
        self.client = None
        self.logger = logging.getLogger(__name__)
        
    def detect_danfe_format(self, text_content: str) -> bool:
        """Detecta se o documento é um DANFE"""
        danfe_indicators = [
            "DANFE",
            "Documento Auxiliar da Nota Fiscal Eletrônica",
            "IDENTIFICAÇÃO DO EMITENTE",
            "DESTINATÁRIO / REMETENTE", 
            "CÁLCULO DO IMPOSTO",
            "DADOS DOS PRODUTOS / SERVIÇOS",
            "BASE DE CÁLC. DO ICMS",
            "VALOR DO ICMS",
            "CHAVE DE ACESSO"
        ]
        
        text_upper = text_content.upper()
        indicators_found = sum(1 for indicator in danfe_indicators if indicator in text_upper)
        
        self.logger.info(f"DANFE indicators found: {indicators_found}/8")
        return indicators_found >= 5
    
    def convert_pdf_to_images(self, pdf_path: str) -> List[str]:
        """Converte PDF para imagens base64 com alta qualidade"""
        images = []
        try:
            doc = fitz.open(pdf_path)
            for page_num in range(len(doc)):
                page = doc[page_num]
                # Usar alta resolução para melhor OCR
                mat = fitz.Matrix(2.0, 2.0)  # 2x zoom para melhor qualidade
                pix = page.get_pixmap(matrix=mat)
                img_data = pix.tobytes("png")
                base64_img = base64.b64encode(img_data).decode('utf-8')
                images.append(base64_img)
            doc.close()
            self.logger.info(f"Converted {len(images)} pages to images")
            return images
        except Exception as e:
            self.logger.error(f"Error converting PDF to images: {e}")
            return []
    
    def extract_danfe_data_with_vision(self, base64_image: str) -> Dict[str, Any]:
        """Extrai dados do DANFE usando GPT-4 Vision com prompt especializado"""
        
        danfe_prompt = """
Você é um especialista em documentos fiscais brasileiros. Analise este DANFE (Documento Auxiliar da Nota Fiscal Eletrônica) e extraia TODOS os dados visíveis com precisão absoluta.

INSTRUÇÕES CRÍTICAS:
1. Leia EXATAMENTE o que está escrito no documento
2. NÃO invente valores - se não conseguir ler, use campo vazio ou 0
3. Mantenha formatação brasileira para valores monetários
4. Extraia dados de TODAS as seções visíveis

SEÇÕES OBRIGATÓRIAS DO DANFE:

**CABEÇALHO E IDENTIFICAÇÃO:**
- Número da NF-e (campo "Nº.")
- Série
- Chave de Acesso (sequência de 44 dígitos)
- Data de Emissão (procure por "Data de Emissão", "DT. EMISSÃO", "EMISSÃO" - formato dd/mm/yyyy)
- Data de Saída/Entrada (procure por "Data de Saída", "DT. SAÍDA", "SAÍDA/ENTRADA" - formato dd/mm/yyyy)
- Protocolo de Autorização

ATENÇÃO ESPECIAL PARA DATAS:
- A Data de Emissão geralmente está no cabeçalho superior do documento
- Pode aparecer como "Data de Emissão:", "DT. EMISSÃO:", ou simplesmente "EMISSÃO:"
- Sempre no formato brasileiro: dd/mm/yyyy (exemplo: 15/03/2024)
- Se aparecer no formato americano mm/dd/yyyy, converta para dd/mm/yyyy
- Leia com cuidado para não confundir com outros números
- Se não conseguir ler claramente, deixe vazio ""

**EMITENTE:**  
- Razão Social
- CNPJ do Emitente
- Endereço completo
- Inscrição Estadual
- Inscrição Municipal

**DESTINATÁRIO:**
- Nome/Razão Social do Destinatário
- CNPJ/CPF do Destinatário
- Endereço completo do Destinatário
- CEP, Município, UF

**CÁLCULO DO IMPOSTO (seção mais importante):**
- Base de Cálc. do ICMS
- Valor do ICMS  
- Base de Cálc. ICMS S.T.
- Valor do ICMS Subst.
- Valor do PIS
- Valor da COFINS
- V. Total Produtos
- Valor do Frete
- Valor do Seguro
- Desconto
- Outras Despesas
- Valor Total IPI
- V. Tot. Trib. (Total de Tributos)
- V. Total da Nota

**PRODUTOS/SERVIÇOS:**
Para cada item na tabela "DADOS DOS PRODUTOS / SERVIÇOS":
- Código do Produto
- Descrição do Produto/Serviço
- NCM/SH
- CST
- CFOP
- Unidade (UN)
- Quantidade
- Valor Unitário
- Valor Total
- Base de Cálculo ICMS
- Valor ICMS
- Alíquota ICMS
- Valor IPI

**TRANSPORTADOR:**
- Nome/Razão Social do Transportador
- CNPJ do Transportador
- Modalidade do Frete
- Placa do Veículo

Responda APENAS em JSON válido com esta estrutura exata:

{
  "numero_nf": "string",
  "serie": "string", 
  "chave_acesso": "string",
  "data_emissao": "dd/mm/yyyy",
  "data_saida_entrada": "dd/mm/yyyy",
  "protocolo_autorizacao": "string",
  
  "razao_social_emitente": "string",
  "cnpj_emitente": "string",
  "endereco_emitente": "string",
  "inscricao_estadual_emitente": "string",
  "inscricao_municipal_emitente": "string",
  
  "razao_social_destinatario": "string", 
  "cnpj_destinatario": "string",
  "endereco_destinatario": "string",
  "cep_destinatario": "string",
  "municipio_destinatario": "string",
  "uf_destinatario": "string",
  
  "base_calculo_icms": 0.00,
  "valor_icms": 0.00,
  "base_calculo_icms_st": 0.00,
  "valor_icms_st": 0.00,
  "valor_pis": 0.00,
  "valor_cofins": 0.00,
  "valor_total_produtos": 0.00,
  "valor_frete": 0.00,
  "valor_seguro": 0.00,
  "valor_desconto": 0.00,
  "outras_despesas": 0.00,
  "valor_total_ipi": 0.00,
  "valor_total_tributos": 0.00,
  "valor_total_nota": 0.00,
  
  "transportador_nome": "string",
  "transportador_cnpj": "string",
  "modalidade_frete": "string",
  "placa_veiculo": "string",
  
  "items": [
    {
      "codigo_produto": "string",
      "descricao_produto": "string", 
      "ncm": "string",
      "cst": "string",
      "cfop": "string",
      "unidade": "string",
      "quantidade": 0.00,
      "valor_unitario": 0.00,
      "valor_total": 0.00,
      "base_calculo_icms": 0.00,
      "valor_icms": 0.00,
      "aliquota_icms": 0.00,
      "valor_ipi": 0.00
    }
  ]
}

IMPORTANTE: Leia com cuidado cada seção e extraia os valores exatos que estão visíveis no documento.
"""

        try:
            if not self.client:
                from openai import OpenAI
                self.client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"), timeout=60.0)
                
            response = self.client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": danfe_prompt},
                            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{base64_image}"}}
                        ]
                    }
                ],
                max_tokens=4000,
                temperature=0.1,
                timeout=60
            )
            
            content = response.choices[0].message.content
            return clean_and_parse_json(content, {})
            
        except Exception as e:
            self.logger.error(f"Error in DANFE vision extraction: {e}")
            return {}
    
    def enhance_date_extraction(self, raw_data: Dict[str, Any], text_content: str, base64_image: str = None) -> Dict[str, Any]:
        """Melhora a extração de datas usando validação aprimorada"""
        
        # Validar e corrigir data de emissão
        emission_date = raw_data.get('data_emissao', '')
        
        # Se não encontrou data na extração principal, tenta métodos especializados
        if not emission_date or emission_date == '':
            self.logger.info("Emission date not found in main extraction, trying specialized methods")
            
            # Método 1: Extrator especializado de data de emissão (mais eficaz)
            try:
                from emission_date_extractor import EmissionDateExtractor
                specialized_extractor = EmissionDateExtractor()
                # Usamos a primeira imagem convertida (assumindo que está disponível)
                emission_date = specialized_extractor.extract_emission_date_only(base64_image)
                if emission_date:
                    self.logger.info(f"Specialized extractor found emission date: {emission_date}")
            except Exception as e:
                self.logger.warning(f"Specialized extractor failed: {e}")
            
            # Método 2: Extração de texto (fallback)
            if not emission_date:
                emission_date = extract_emission_date_from_text(text_content)
                self.logger.info(f"Text extraction found emission date: {emission_date}")
        else:
            # Validar e corrigir se necessário
            corrected_date = validate_and_correct_date(emission_date, 'data_emissao')
            if corrected_date:
                emission_date = corrected_date
            else:
                # Fallback para extração especializada
                try:
                    from emission_date_extractor import EmissionDateExtractor
                    specialized_extractor = EmissionDateExtractor()
                    fallback_date = specialized_extractor.extract_emission_date_only(base64_image)
                    if fallback_date:
                        emission_date = fallback_date
                        self.logger.info(f"Fallback to specialized extractor: {emission_date}")
                except Exception as e:
                    self.logger.warning(f"Fallback specialized extractor failed: {e}")
        
        # Validar e corrigir data de saída/entrada
        exit_date = raw_data.get('data_saida_entrada', '')
        if exit_date:
            corrected_exit_date = validate_and_correct_date(exit_date, 'data_saida_entrada')
            if corrected_exit_date:
                exit_date = corrected_exit_date
            else:
                self.logger.warning(f"Could not validate exit date: {exit_date}")
                exit_date = ''
        
        # Atualizar dados com datas corrigidas
        raw_data['data_emissao'] = emission_date or ''
        raw_data['data_saida_entrada'] = exit_date or ''
        
        return raw_data

    def normalize_danfe_data(self, raw_data: Dict[str, Any]) -> Dict[str, Any]:
        """Normaliza dados do DANFE para formato do banco de dados"""
        
        # Mapeamento específico para campos DANFE -> Database
        normalized = {
            # Identificação do documento
            'numero_nf': raw_data.get('numero_nf', ''),
            'serie': raw_data.get('serie', ''),
            'chave_acesso': raw_data.get('chave_acesso', ''),
            'data_emissao': raw_data.get('data_emissao', ''),
            'data_saida_entrada': raw_data.get('data_saida_entrada', ''),
            'protocolo_autorizacao': raw_data.get('protocolo_autorizacao', ''),
            
            # Emitente  
            'razao_social_emitente': raw_data.get('razao_social_emitente', ''),
            'cnpj_emitente': raw_data.get('cnpj_emitente', ''),
            'endereco_emitente': raw_data.get('endereco_emitente', ''),
            'inscricao_estadual_emitente': raw_data.get('inscricao_estadual_emitente', ''),
            'inscricao_municipal_emitente': raw_data.get('inscricao_municipal_emitente', ''),
            
            # Destinatário
            'destinatario_nome': raw_data.get('razao_social_destinatario', ''),
            'destinatario_cnpj': raw_data.get('cnpj_destinatario', ''),
            'destinatario_endereco': raw_data.get('endereco_destinatario', ''),
            'destinatario_cep': raw_data.get('cep_destinatario', ''),
            'destinatario_municipio': raw_data.get('municipio_destinatario', ''),
            'destinatario_uf': raw_data.get('uf_destinatario', ''),
            
            # Valores fiscais (principais)
            'valor_total_produtos': self._parse_decimal(raw_data.get('valor_total_produtos', 0)),
            'valor_total_nf': self._parse_decimal(raw_data.get('valor_total_nota', 0)),
            'valor_frete': self._parse_decimal(raw_data.get('valor_frete', 0)),
            'valor_seguro': self._parse_decimal(raw_data.get('valor_seguro', 0)),
            'valor_desconto': self._parse_decimal(raw_data.get('valor_desconto', 0)),
            'valor_tributos': self._parse_decimal(raw_data.get('valor_total_tributos', 0)),
            
            # Impostos ICMS
            'base_calculo_icms': self._parse_decimal(raw_data.get('base_calculo_icms', 0)),
            'valor_icms': self._parse_decimal(raw_data.get('valor_icms', 0)),
            'base_calculo_icms_st': self._parse_decimal(raw_data.get('base_calculo_icms_st', 0)),
            'valor_icms_st': self._parse_decimal(raw_data.get('valor_icms_st', 0)),
            
            # Impostos federais
            'valor_pis': self._parse_decimal(raw_data.get('valor_pis', 0)),
            'valor_cofins': self._parse_decimal(raw_data.get('valor_cofins', 0)),
            'valor_ipi': self._parse_decimal(raw_data.get('valor_total_ipi', 0)),
            
            # Transportador
            'transportadora_nome': raw_data.get('transportador_nome', ''),
            'transportadora_cnpj': raw_data.get('transportador_cnpj', ''),
            'modalidade_frete': raw_data.get('modalidade_frete', ''),
            'placa_veiculo': raw_data.get('placa_veiculo', ''),
            
            # Items
            'items': self._normalize_items(raw_data.get('items', []))
        }
        
        # Aplicar limpeza de datas
        normalized = clean_date_fields(normalized)
        
        return normalized
    
    def _normalize_items(self, items_data: List[Dict]) -> List[Dict]:
        """Normaliza dados dos itens"""
        normalized_items = []
        
        for item in items_data:
            normalized_item = {
                'codigo_produto': item.get('codigo_produto', ''),
                'descricao_produto': item.get('descricao_produto', ''),
                'ncm': item.get('ncm', ''),
                'cst': item.get('cst', ''),
                'cfop': item.get('cfop', ''),
                'unidade_comercial': item.get('unidade', ''),
                'quantidade_comercial': self._parse_decimal(item.get('quantidade', 0)),
                'valor_unitario_comercial': self._parse_decimal(item.get('valor_unitario', 0)),
                'valor_total_produto': self._parse_decimal(item.get('valor_total', 0)),
                'tax_base_calculo': self._parse_decimal(item.get('base_calculo_icms', 0)),
                'valor_icms_item': self._parse_decimal(item.get('valor_icms', 0)),
                'aliquota_icms': self._parse_decimal(item.get('aliquota_icms', 0)),
                'valor_ipi_item': self._parse_decimal(item.get('valor_ipi', 0))
            }
            normalized_items.append(normalized_item)
            
        return normalized_items
    
    def _parse_decimal(self, value) -> float:
        """Parse valor decimal brasileiro"""
        if not value:
            return 0.0
        
        try:
            if isinstance(value, (int, float)):
                return float(value)
            
            # Remove caracteres não numéricos exceto vírgula e ponto
            value_str = str(value).replace('R$', '').replace(' ', '').strip()
            
            # Converte vírgula decimal brasileira para ponto
            if ',' in value_str and '.' in value_str:
                # Formato: 1.234.567,89
                value_str = value_str.replace('.', '').replace(',', '.')
            elif ',' in value_str:
                # Formato: 1234,89
                value_str = value_str.replace(',', '.')
            
            return float(value_str)
        except:
            return 0.0
    
    def process_danfe_pdf(self, pdf_path: str, original_filename: str) -> Dict[str, Any]:
        """Processa um PDF DANFE completo"""
        
        self.logger.info(f"Starting DANFE processing for {original_filename}")
        
        try:
            # Converter PDF para imagens
            images = self.convert_pdf_to_images(pdf_path)
            if not images:
                return {'success': False, 'error': 'Could not convert PDF to images'}
            
            # Processar primeira página (DANFE geralmente é 1 página)
            base64_image = images[0]
            
            # Extrair texto para validação de datas
            doc = fitz.open(pdf_path)
            text_content = ""
            for page in doc:
                text_content += page.get_text()
            doc.close()
            
            # Extrair dados com GPT-4 Vision
            raw_data = self.extract_danfe_data_with_vision(base64_image)
            
            if not raw_data:
                return {'success': False, 'error': 'Could not extract data from DANFE'}
            
            # Melhorar extração de datas com validação
            raw_data = self.enhance_date_extraction(raw_data, text_content, base64_image)
            
            # Normalizar dados
            normalized_data = self.normalize_danfe_data(raw_data)
            
            # Classificar tipo de operação
            try:
                from document_type_classifier import classify_document_operation_type
                operation_type = classify_document_operation_type(base64_image, normalized_data)
                normalized_data['tipo_operacao'] = operation_type
                self.logger.info(f"DANFE classified as: {operation_type}")
            except Exception as e:
                self.logger.warning(f"Operation type classification failed: {e}")
                normalized_data['tipo_operacao'] = "Serviços e Produtos"
            
            self.logger.info(f"DANFE processing successful for {original_filename}")
            self.logger.info(f"Extracted fields: {list(normalized_data.keys())}")
            
            return {
                'success': True,
                'data': normalized_data,
                'confidence_score': 0.95,  # Alto para processador especializado
                'processing_notes': [f'DANFE processing with specialized extractor'],
                'document_format': 'DANFE'
            }
            
        except Exception as e:
            self.logger.error(f"Error processing DANFE {original_filename}: {e}")
            return {'success': False, 'error': str(e)}


def process_danfe_pdf(pdf_path: str, original_filename: str) -> Dict[str, Any]:
    """
    Função principal para processar PDFs DANFE
    
    Args:
        pdf_path: Caminho para o arquivo PDF
        original_filename: Nome original do arquivo
        
    Returns:
        Resultado do processamento
    """
    processor = DANFEProcessor()
    return processor.process_danfe_pdf(pdf_path, original_filename)


def detect_if_danfe(pdf_path: str) -> bool:
    """
    Detecta se um PDF é um DANFE
    
    Args:
        pdf_path: Caminho para o arquivo PDF
        
    Returns:
        True se for DANFE, False caso contrário
    """
    try:
        doc = fitz.open(pdf_path)
        text_content = ""
        for page_num in range(min(2, len(doc))):  # Primeiras 2 páginas
            page = doc[page_num]
            text_content += page.get_text()
        doc.close()
        
        processor = DANFEProcessor()
        return processor.detect_danfe_format(text_content)
    except:
        return False