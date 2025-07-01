"""
Enhanced Universal PDF Processor
Intelligent document format detection and processing with format-specific extraction strategies
"""

import os
import base64
import logging
import re
from typing import Dict, Any, List, Optional
from openai import OpenAI
# Using universal_pdf_simple for PDF processing instead of PyMuPDF to avoid import issues
from json_cleaner import clean_and_parse_json
from date_utils import clean_date_fields

logger = logging.getLogger(__name__)

class EnhancedUniversalProcessor:
    """Enhanced processor with intelligent format detection and specific extraction strategies"""
    
    def __init__(self):
        self.client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
        
        # Document format patterns for detection
        self.format_patterns = {
            'danfe': [
                r'DANFE',
                r'Documento Auxiliar da Nota Fiscal Eletrônica',
                r'NF-e',
                r'CHAVE DE ACESSO',
                r'CÁLCULO DO IMPOSTO',
                r'BASE DE CÁLC\. DO ICMS'
            ],
            'nfse': [
                r'Nota Fiscal de Serviço Eletrônica',
                r'NFS-e',
                r'TOMADOR DO SERVIÇO',
                r'DESCRIÇÃO DOS SERVIÇOS PRESTADOS',
                r'Local Prestação',
                r'ISSQN'
            ],
            'terminal_portuario': [
                r'TERMINAL PORTUARIO',
                r'PORTO',
                r'LEVANTE DE CONTÊINER',
                r'SCANNER',
                r'UTILIZAÇÃO DE SCANNER'
            ],
            'cross_dock': [
                r'CROSS DOCK',
                r'CROSS-DOCK',
                r'ARMAZENAGEM',
                r'MOVIMENTAÇÃO'
            ]
        }
    
    def detect_document_format(self, text_content: str) -> str:
        """Detect document format based on text patterns"""
        text_upper = text_content.upper()
        
        # Count matches for each format
        format_scores = {}
        for format_name, patterns in self.format_patterns.items():
            score = 0
            for pattern in patterns:
                if re.search(pattern, text_upper):
                    score += 1
            format_scores[format_name] = score
        
        # Return format with highest score, or 'generic' if no clear match
        if format_scores:
            best_format = max(format_scores.keys(), key=lambda k: format_scores[k])
            if format_scores[best_format] > 0:
                logger.info(f"Detected document format: {best_format} (score: {format_scores[best_format]})")
                return best_format
        
        logger.info("No specific format detected, using generic processing")
        return 'generic'
    
    def get_format_specific_prompt(self, document_format: str) -> str:
        """Get GPT prompt optimized for specific document format"""
        
        base_instruction = """Você é um especialista em análise de documentos fiscais brasileiros. 
Analise cuidadosamente esta imagem de documento fiscal e extraia TODAS as informações visíveis.

IMPORTANTE: 
- Leia apenas o que está claramente visível no documento
- NÃO invente ou estime valores que não estão claramente mostrados
- Se um campo não estiver visível, deixe em branco ou null
- Mantenha a formatação brasileira para valores monetários
- Para datas, use o formato dd/mm/yyyy se mostrado dessa forma

"""
        
        if document_format == 'danfe':
            return base_instruction + """
FORMATO DETECTADO: DANFE (Documento Auxiliar da Nota Fiscal Eletrônica)

Este é um documento DANFE de NFe. Extraia especificamente:

IDENTIFICAÇÃO DO DOCUMENTO:
- Número da NF-e, Série, Folha
- Chave de acesso (sequência de 44 dígitos)
- Data de emissão, Data de saída/entrada
- Natureza da operação

EMITENTE:
- Razão social, CNPJ, Inscrição Estadual
- Endereço completo (rua, bairro, CEP, cidade, estado)

DESTINATÁRIO:
- Razão social, CNPJ, Inscrição Estadual  
- Endereço completo

PRODUTOS/SERVIÇOS (tabela "DADOS DOS PRODUTOS/SERVIÇOS"):
- Para cada item: código, descrição, NCM, CFOP, unidade, quantidade, valor unitário, valor total
- CST, alíquotas de ICMS e IPI

IMPOSTOS (seção "CÁLCULO DO IMPOSTO"):
- Base de Cálculo do ICMS, Valor do ICMS
- Valor do IPI, Valor do PIS, Valor da COFINS
- Valor Total dos Produtos, Valor Total da Nota

TRANSPORTADOR:
- Nome, CNPJ, endereço, placa do veículo

VOLUMES:
- Quantidade, espécie, peso bruto, peso líquido

Responda em JSON estruturado."""

        elif document_format == 'nfse':
            return base_instruction + """
FORMATO DETECTADO: NFS-e (Nota Fiscal de Serviço Eletrônica)

Este é um documento de Nota Fiscal de Serviços. Extraia especificamente:

IDENTIFICAÇÃO:
- Número da NFS-e, Série
- Data do fato gerador, Data/hora de emissão
- Identificador (chave de acesso)

PRESTADOR:
- Razão social, CNPJ
- Endereço completo, CEP, cidade, estado
- Inscrição Municipal, Inscrição Estadual

TOMADOR:
- Razão social, CNPJ/CPF
- Endereço completo, CEP, cidade, estado

SERVIÇOS (seção "DESCRIÇÃO DOS SERVIÇOS PRESTADOS"):
- Código do serviço, Local de prestação
- Alíquota, Valor do serviço
- Descrição detalhada do serviço

IMPOSTOS E RETENÇÕES:
- ISSQN (ISS), ISSRF
- IR (Imposto de Renda), INSS, CSLL
- COFINS, PIS
- Outras retenções

TOTAIS:
- Valor total, Base de cálculo
- Deduções, Descontos
- Valor líquido

Responda em JSON estruturado."""

        elif document_format == 'terminal_portuario':
            return base_instruction + """
FORMATO DETECTADO: Terminal Portuário

Este é um documento de serviços portuários. Extraia especificamente:

IDENTIFICAÇÃO:
- Número do documento, série, data de emissão

PRESTADOR DE SERVIÇOS:
- Nome da empresa, CNPJ
- Endereço completo

TOMADOR:
- Razão social, CNPJ
- Endereço

SERVIÇOS PORTUÁRIOS:
- Código e descrição dos serviços (ex: LEVANTE DE CONTÊINER, SCANNER)
- Quantidade, unidade (UN, etc.)
- Valor unitário, valor total por serviço

IMPOSTOS:
- Valores de retenções (IR, INSS, PIS, COFINS, CSLL, ISSQN)
- Base de cálculo dos impostos

TOTAIS:
- Valor bruto dos serviços
- Total dos impostos retidos
- Valor líquido

Responda em JSON estruturado."""

        else:  # generic
            return base_instruction + """
FORMATO: Documento fiscal genérico

Extraia todas as informações fiscais visíveis:

IDENTIFICAÇÃO:
- Número do documento, série, data

EMITENTE/PRESTADOR:
- Razão social, CNPJ, endereço

DESTINATÁRIO/TOMADOR:
- Razão social, CNPJ, endereço

ITENS/SERVIÇOS:
- Descrição, quantidade, valores

IMPOSTOS:
- Todos os valores de impostos visíveis

TOTAIS:
- Valores brutos, líquidos, impostos

Responda em JSON estruturado."""

    def extract_text_from_pdf(self, pdf_path: str) -> str:
        """Extract text content from PDF for format detection using universal processor"""
        try:
            # Use the existing universal processor to get text content
            from universal_pdf_simple import UniversalPDFSimple
            processor = UniversalPDFSimple()
            
            # Convert first page to image and extract text with GPT for format detection
            images = processor.convert_pdf_to_images(pdf_path)
            if images:
                # Use a simple extraction prompt to get text content
                response = self.client.chat.completions.create(
                    model="gpt-4o",
                    messages=[
                        {
                            "role": "user", 
                            "content": [
                                {"type": "text", "text": "Extraia todo o texto visível neste documento fiscal brasileiro. Responda apenas com o texto extraído, sem formatação adicional."},
                                {
                                    "type": "image_url",
                                    "image_url": {"url": f"data:image/png;base64,{images[0]}"}
                                }
                            ]
                        }
                    ],
                    max_tokens=2000,
                    temperature=0
                )
                return response.choices[0].message.content or ""
            return ""
        except Exception as e:
            logger.error(f"Error extracting text from PDF: {e}")
            return ""

    def convert_pdf_to_images(self, pdf_path: str) -> List[str]:
        """Convert PDF pages to base64 encoded images using existing processor"""
        try:
            from universal_pdf_simple import UniversalPDFSimple
            processor = UniversalPDFSimple()
            return processor.convert_pdf_to_images(pdf_path)
        except Exception as e:
            logger.error(f"Error converting PDF to images: {e}")
            return []

    def extract_data_with_vision(self, base64_image: str, document_format: str) -> Dict[str, Any]:
        """Extract data from image using GPT-4 Vision with format-specific prompt"""
        try:
            prompt = self.get_format_specific_prompt(document_format)
            
            response = self.client.chat.completions.create(
                model="gpt-4o",  # Latest model
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
                max_tokens=4000,
                temperature=0.1  # Lower temperature for more consistent extraction
            )
            
            content = response.choices[0].message.content
            logger.info(f"GPT-4 Vision response received for {document_format} format")
            
            # Clean and parse JSON response
            extracted_data = clean_and_parse_json(content, {})
            
            if not extracted_data:
                logger.warning("Failed to parse JSON from GPT response")
                return {}
                
            return extracted_data
            
        except Exception as e:
            logger.error(f"Error in GPT-4 Vision extraction: {e}")
            return {}

    def normalize_extracted_data(self, raw_data: Dict[str, Any], document_format: str) -> Dict[str, Any]:
        """Normalize extracted data to database-compatible format"""
        try:
            normalized = {}
            
            # Standard field mappings based on format
            if document_format == 'danfe':
                # DANFE specific mappings
                if 'identificacao' in raw_data:
                    id_data = raw_data['identificacao']
                    normalized['numero_nf'] = str(id_data.get('numero', ''))
                    normalized['serie'] = str(id_data.get('serie', ''))
                    normalized['chave_acesso'] = str(id_data.get('chave_acesso', ''))
                
                if 'emitente' in raw_data:
                    emit_data = raw_data['emitente']
                    normalized['razao_social_emitente'] = str(emit_data.get('razao_social', ''))
                    normalized['cnpj_emitente'] = str(emit_data.get('cnpj', ''))
                    normalized['endereco_emitente'] = str(emit_data.get('endereco_completo', ''))
                
                if 'destinatario' in raw_data:
                    dest_data = raw_data['destinatario']
                    normalized['razao_social_destinatario'] = str(dest_data.get('razao_social', ''))
                    normalized['cnpj_destinatario'] = str(dest_data.get('cnpj', ''))
                
                if 'impostos' in raw_data:
                    imp_data = raw_data['impostos']
                    normalized['valor_icms'] = float(imp_data.get('valor_icms', 0) or 0)
                    normalized['valor_ipi'] = float(imp_data.get('valor_ipi', 0) or 0)
                    normalized['valor_pis'] = float(imp_data.get('valor_pis', 0) or 0)
                    normalized['valor_cofins'] = float(imp_data.get('valor_cofins', 0) or 0)
                
                if 'totais' in raw_data:
                    tot_data = raw_data['totais']
                    normalized['valor_total_produtos'] = float(tot_data.get('valor_total_produtos', 0) or 0)
                    normalized['valor_total_nota'] = float(tot_data.get('valor_total_nota', 0) or 0)
            
            elif document_format == 'nfse':
                # NFS-e specific mappings
                if 'identificacao' in raw_data:
                    id_data = raw_data['identificacao']
                    normalized['numero_nf'] = str(id_data.get('numero_nfse', ''))
                    normalized['serie'] = str(id_data.get('serie', ''))
                
                if 'prestador' in raw_data:
                    prest_data = raw_data['prestador']
                    normalized['razao_social_emitente'] = str(prest_data.get('razao_social', ''))
                    normalized['cnpj_emitente'] = str(prest_data.get('cnpj', ''))
                    normalized['endereco_emitente'] = str(prest_data.get('endereco_completo', ''))
                
                if 'tomador' in raw_data:
                    tom_data = raw_data['tomador']
                    normalized['razao_social_destinatario'] = str(tom_data.get('razao_social', ''))
                    normalized['cnpj_destinatario'] = str(tom_data.get('cnpj', ''))
                
                if 'impostos' in raw_data:
                    imp_data = raw_data['impostos']
                    normalized['valor_issqn'] = float(imp_data.get('issqn', 0) or 0)
                    normalized['valor_ir'] = float(imp_data.get('ir', 0) or 0)
                    normalized['valor_inss'] = float(imp_data.get('inss', 0) or 0)
                    normalized['valor_csll'] = float(imp_data.get('csll', 0) or 0)
                    normalized['valor_cofins'] = float(imp_data.get('cofins', 0) or 0)
                    normalized['valor_pis'] = float(imp_data.get('pis', 0) or 0)
                
                if 'totais' in raw_data:
                    tot_data = raw_data['totais']
                    normalized['valor_total_servicos'] = float(tot_data.get('valor_total', 0) or 0)
                    normalized['valor_total_nota'] = float(tot_data.get('valor_liquido', 0) or 0)
            
            else:
                # Generic mapping - try to map common fields
                for key, value in raw_data.items():
                    if isinstance(value, dict):
                        # Flatten nested dictionaries
                        for sub_key, sub_value in value.items():
                            field_name = f"{key}_{sub_key}".lower()
                            normalized[field_name] = sub_value
                    else:
                        normalized[key.lower()] = value
            
            # Extract items data
            items = []
            if 'produtos' in raw_data:
                for item in raw_data['produtos']:
                    normalized_item = {
                        'codigo': str(item.get('codigo', '')),
                        'descricao': str(item.get('descricao', '')),
                        'quantidade': float(item.get('quantidade', 0) or 0),
                        'valor_unitario': float(item.get('valor_unitario', 0) or 0),
                        'valor_total': float(item.get('valor_total', 0) or 0),
                        'ncm': str(item.get('ncm', '')),
                        'cfop': str(item.get('cfop', '')),
                        'cst': str(item.get('cst', ''))
                    }
                    items.append(normalized_item)
            
            elif 'servicos' in raw_data:
                for item in raw_data['servicos']:
                    normalized_item = {
                        'codigo': str(item.get('codigo_servico', '')),
                        'descricao': str(item.get('descricao', '')),
                        'quantidade': float(item.get('quantidade', 1) or 1),
                        'valor_unitario': float(item.get('valor_unitario', 0) or 0),
                        'valor_total': float(item.get('valor_total', 0) or 0),
                        'codigo_servico': str(item.get('codigo_servico', '')),
                        'aliquota': float(item.get('aliquota', 0) or 0)
                    }
                    items.append(normalized_item)
            
            elif 'itens' in raw_data:
                for item in raw_data['itens']:
                    normalized_item = {
                        'codigo': str(item.get('codigo', '')),
                        'descricao': str(item.get('descricao', '')),
                        'quantidade': float(item.get('quantidade', 0) or 0),
                        'valor_unitario': float(item.get('valor_unitario', 0) or 0),
                        'valor_total': float(item.get('valor_total', 0) or 0)
                    }
                    items.append(normalized_item)
            
            normalized['items'] = items
            
            # Extract dates
            date_fields = ['data_emissao', 'data_vencimento', 'data_saida', 'data_entrada']
            for field in date_fields:
                if field in raw_data:
                    normalized[field] = raw_data[field]
            
            logger.info(f"Normalized {len(normalized)} fields and {len(items)} items for {document_format}")
            return normalized
            
        except Exception as e:
            logger.error(f"Error normalizing data: {e}")
            return {'items': []}

    def process_pdf_enhanced(self, pdf_path: str, original_filename: str) -> Dict[str, Any]:
        """Enhanced PDF processing with intelligent format detection"""
        try:
            logger.info(f"Starting enhanced processing for {original_filename}")
            
            # Step 1: Extract text for format detection
            text_content = self.extract_text_from_pdf(pdf_path)
            document_format = self.detect_document_format(text_content)
            
            # Step 2: Convert PDF to images
            images = self.convert_pdf_to_images(pdf_path)
            if not images:
                raise Exception("Failed to convert PDF to images")
            
            # Step 3: Process each page with format-specific strategy
            all_page_data = []
            for i, base64_image in enumerate(images):
                logger.info(f"Processing page {i+1}/{len(images)} with {document_format} format")
                page_data = self.extract_data_with_vision(base64_image, document_format)
                
                if page_data:
                    page_data['page_number'] = i + 1
                    all_page_data.append(page_data)
            
            if not all_page_data:
                raise Exception("No data extracted from any page")
            
            # Step 4: Consolidate data from all pages
            consolidated_data = self.consolidate_multi_page_data(all_page_data, document_format)
            
            # Step 5: Normalize to database format
            normalized_data = self.normalize_extracted_data(consolidated_data, document_format)
            
            # Step 6: Apply date cleaning
            normalized_data = clean_date_fields(normalized_data)
            
            result = {
                'success': True,
                'data': normalized_data,
                'confidence_score': 0.95,  # High confidence for enhanced processing
                'pages_processed': len(images),
                'document_format': document_format,
                'processing_notes': [
                    f'Enhanced processing with {document_format} format detection',
                    f'Processed {len(images)} pages successfully',
                    f'Extracted {len(normalized_data.get("items", []))} items'
                ]
            }
            
            logger.info(f"Enhanced processing completed for {original_filename} - Format: {document_format}")
            return result
            
        except Exception as e:
            error_msg = f"Enhanced processing failed: {str(e)}"
            logger.error(error_msg)
            
            return {
                'success': False,
                'error': error_msg,
                'confidence_score': 0.0,
                'pages_processed': 0,
                'processing_notes': [error_msg]
            }

    def consolidate_multi_page_data(self, all_page_data: List[Dict[str, Any]], document_format: str) -> Dict[str, Any]:
        """Consolidate data from multiple pages intelligently"""
        if not all_page_data:
            return {}
        
        if len(all_page_data) == 1:
            # Single page, return as-is
            result = all_page_data[0].copy()
            result.pop('page_number', None)
            return result
        
        # Multi-page consolidation
        consolidated = all_page_data[0].copy()
        consolidated.pop('page_number', None)
        
        # Merge items from all pages
        all_items = []
        items_key = 'produtos' if 'produtos' in consolidated else 'servicos' if 'servicos' in consolidated else 'itens'
        
        for page_data in all_page_data:
            page_items = page_data.get(items_key, [])
            if isinstance(page_items, list):
                all_items.extend(page_items)
        
        if all_items and items_key:
            consolidated[items_key] = all_items
        
        logger.info(f"Consolidated {len(all_page_data)} pages with {len(all_items)} total items")
        return consolidated


def process_pdf_enhanced_universal(pdf_path: str, original_filename: str) -> Dict[str, Any]:
    """
    Enhanced universal PDF processing with intelligent format detection
    
    Args:
        pdf_path: Path to PDF file
        original_filename: Original filename for logging
        
    Returns:
        Processing result with enhanced format-specific extraction
    """
    processor = EnhancedUniversalProcessor()
    return processor.process_pdf_enhanced(pdf_path, original_filename)