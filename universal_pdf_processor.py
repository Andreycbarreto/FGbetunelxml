"""
Universal PDF NFe Processor
Advanced multi-stage PDF processing system designed to handle ANY NFe PDF format
with intelligent layout detection and adaptive data extraction.
"""

import os
import base64
import logging
import json
from typing import Dict, Any, List, Optional
from openai import OpenAI
import pymupdf
from dataclasses import dataclass

logger = logging.getLogger(__name__)

@dataclass
class NFELayout:
    """Represents different NFe layout patterns"""
    name: str
    indicators: List[str]  # Text patterns that indicate this layout
    extraction_strategy: str
    confidence: float = 0.0

class UniversalPDFProcessor:
    """Universal PDF processor that adapts to any NFe format."""
    
    def __init__(self):
        self.client = OpenAI(
            api_key=os.environ.get("OPENAI_API_KEY"),
            timeout=90.0  # Extended timeout for complex processing
        )
        self.logger = logging.getLogger(__name__)
        
        # Define known NFe layout patterns
        self.known_layouts = [
            NFELayout("danfe_portrait", ["DANFE", "Documento Auxiliar"], "portrait_standard"),
            NFELayout("danfe_landscape", ["DANFE", "formato paisagem"], "landscape_standard"),
            NFELayout("simplified", ["NFCe", "Cupom Fiscal"], "simplified_receipt"),
            NFELayout("service_nfse", ["NFSE", "Serviços"], "service_document"),
            NFELayout("government", ["Prefeitura", "Municipal"], "government_format"),
            NFELayout("corporate", ["CNPJ", "Razão Social"], "corporate_standard"),
        ]
    
    def process_pdf_universal(self, file_path: str) -> Dict[str, Any]:
        """
        Universal PDF processing that adapts to any NFe format.
        
        Args:
            file_path (str): Path to the PDF file
            
        Returns:
            dict: Extracted NFe data regardless of format
        """
        try:
            self.logger.info(f"Starting universal PDF processing for: {file_path}")
            
            # Step 1: Convert PDF to high-quality images
            pdf_images = self._convert_pdf_to_high_quality_images(file_path)
            
            if not pdf_images:
                raise Exception("Failed to convert PDF to images")
            
            # Step 2: Detect document layout and type
            layout_info = self._detect_document_layout(pdf_images[0])
            self.logger.info(f"Detected layout: {layout_info}")
            
            # Step 3: Multi-stage extraction adapted to layout
            extracted_data = self._extract_with_adaptive_strategy(pdf_images, layout_info)
            
            # Step 4: Validate and consolidate data
            final_data = self._validate_and_consolidate(extracted_data)
            
            # Step 5: Extract items with layout-aware processing
            items_data = self._extract_items_universal(pdf_images, layout_info)
            final_data['items'] = items_data
            
            # Step 6: Extract taxes with format-aware processing
            tax_data = self._extract_taxes_universal(pdf_images, layout_info, final_data.get('valor_total_servicos', 0))
            final_data.update(tax_data)
            
            self.logger.info("Universal PDF processing completed successfully")
            return {
                'success': True,
                'data': final_data,
                'confidence_score': layout_info.get('confidence', 0.8),
                'processing_notes': [f"Layout detected: {layout_info.get('layout_type', 'unknown')}"]
            }
            
        except Exception as e:
            self.logger.error(f"Universal PDF processing failed: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'data': {}
            }
    
    def _convert_pdf_to_high_quality_images(self, file_path: str) -> List[str]:
        """Convert PDF pages to high-quality base64 images."""
        try:
            pdf_document = pymupdf.open(file_path)
            images = []
            
            for page_num in range(len(pdf_document)):
                page = pdf_document[page_num]
                
                # Use high DPI for better OCR quality
                mat = pymupdf.Matrix(2.0, 2.0)  # 2x zoom for better quality
                pix = page.get_pixmap(matrix=mat, alpha=False)
                
                img_data = pix.tobytes("png")
                img_base64 = base64.b64encode(img_data).decode()
                images.append(img_base64)
                
                # Focus on first 2 pages for NFe (usually sufficient)
                if page_num >= 1:
                    break
            
            pdf_document.close()
            return images
            
        except Exception as e:
            self.logger.error(f"Error converting PDF to images: {str(e)}")
            return []
    
    def _detect_document_layout(self, image_base64: str) -> Dict[str, Any]:
        """Detect the document layout and format type."""
        try:
            response = self.client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {
                        "role": "system",
                        "content": """Você é um especialista em análise de documentos fiscais brasileiros.
                        Analise esta imagem de NFe e identifique:
                        
                        1. TIPO DE LAYOUT:
                        - portrait_standard: DANFE vertical padrão
                        - landscape_standard: DANFE horizontal
                        - simplified_receipt: NFCe ou cupom fiscal
                        - service_document: NFSE ou documento de serviços
                        - government_format: Formato de prefeitura/governo
                        - custom_format: Formato personalizado
                        
                        2. CARACTERÍSTICAS:
                        - Orientação (vertical/horizontal)
                        - Número de colunas
                        - Posição dos dados principais
                        - Tipo de documento (NFe, NFCe, NFSE)
                        
                        3. ELEMENTOS IDENTIFICÁVEIS:
                        - Logo/cabeçalho
                        - Códigos de barras/QR codes
                        - Tabelas de itens
                        - Área de impostos
                        - Informações do emitente/destinatário
                        
                        Responda APENAS em JSON com esta estrutura:
                        {
                            "layout_type": "tipo_detectado",
                            "orientation": "portrait|landscape",
                            "document_type": "NFe|NFCe|NFSE",
                            "has_items_table": true|false,
                            "has_tax_section": true|false,
                            "complexity": "simple|medium|complex",
                            "confidence": 0.0-1.0,
                            "key_sections": ["secao1", "secao2"],
                            "extraction_hints": ["dica1", "dica2"]
                        }"""
                    },
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": "Analise este documento fiscal e identifique seu layout e características:"
                            },
                            {
                                "type": "image_url",
                                "image_url": {"url": f"data:image/png;base64,{image_base64}"}
                            }
                        ]
                    }
                ],
                max_tokens=1000,
                temperature=0.1
            )
            
            content = response.choices[0].message.content
            if content:
                layout_analysis = json.loads(content)
                return layout_analysis
            else:
                raise Exception("Empty response from layout detection")
            
        except Exception as e:
            self.logger.error(f"Layout detection failed: {str(e)}")
            return {
                "layout_type": "custom_format",
                "orientation": "portrait",
                "document_type": "NFe",
                "confidence": 0.5,
                "complexity": "medium"
            }
    
    def _extract_with_adaptive_strategy(self, images: List[str], layout_info: Dict) -> Dict[str, Any]:
        """Extract data using strategy adapted to detected layout."""
        
        layout_type = layout_info.get('layout_type', 'custom_format')
        complexity = layout_info.get('complexity', 'medium')
        
        # Choose extraction strategy based on layout
        if layout_type in ['portrait_standard', 'landscape_standard']:
            return self._extract_standard_danfe(images[0], layout_info)
        elif layout_type == 'service_document':
            return self._extract_service_document(images[0], layout_info)
        elif layout_type == 'simplified_receipt':
            return self._extract_simplified_format(images[0], layout_info)
        else:
            # Universal fallback strategy for unknown formats
            return self._extract_universal_fallback(images[0], layout_info)
    
    def _extract_standard_danfe(self, image_base64: str, layout_info: Dict) -> Dict[str, Any]:
        """Extract data from standard DANFE format."""
        try:
            response = self.client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {
                        "role": "system",
                        "content": """Você é um especialista em extração de dados de DANFE (Documento Auxiliar da NFe).
                        
                        Este é um DANFE padrão. Extraia TODOS os dados visíveis seguindo a estrutura brasileira:
                        
                        SEÇÕES OBRIGATÓRIAS:
                        1. IDENTIFICAÇÃO: Número, série, data/hora emissão, chave de acesso
                        2. EMITENTE: CNPJ, razão social, endereço completo, IE
                        3. DESTINATÁRIO: CNPJ/CPF, nome, endereço, IE
                        4. VALORES: Valor total, base cálculo, ICMS, IPI, etc.
                        5. TRANSPORTADORA: Se houver
                        6. INFORMAÇÕES ADICIONAIS: Observações importantes
                        
                        REGRAS CRÍTICAS:
                        - Extraia números exatamente como aparecem
                        - Preserve formatação de CNPJ/CPF (XX.XXX.XXX/XXXX-XX)
                        - Mantenha datas no formato brasileiro (DD/MM/AAAA)
                        - Valores com vírgula decimal brasileira
                        - Se não encontrar um campo, use null
                        
                        Responda APENAS em JSON válido com TODOS os campos."""
                    },
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text", 
                                "text": "Extraia todos os dados deste DANFE padrão:"
                            },
                            {
                                "type": "image_url",
                                "image_url": {"url": f"data:image/png;base64,{image_base64}"}
                            }
                        ]
                    }
                ],
                max_tokens=2000,
                temperature=0.05  # Very low temperature for precision
            )
            
            content = response.choices[0].message.content
            if content:
                return json.loads(content)
            else:
                return {}
            
        except Exception as e:
            self.logger.error(f"Standard DANFE extraction failed: {str(e)}")
            return {}
    
    def _extract_service_document(self, image_base64: str, layout_info: Dict) -> Dict[str, Any]:
        """Extract data from service documents (NFSE, etc.)."""
        try:
            response = self.client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {
                        "role": "system",
                        "content": """Você é especialista em extração de dados de documentos de SERVIÇOS (NFSE, RPS).
                        
                        Este documento é de PRESTAÇÃO DE SERVIÇOS. Foque nos campos específicos:
                        
                        CAMPOS PRIORITÁRIOS PARA SERVIÇOS:
                        1. IDENTIFICAÇÃO: Número RPS/NFSE, competência, série
                        2. PRESTADOR: CNPJ, razão social, IM (Inscrição Municipal)
                        3. TOMADOR: CNPJ/CPF, nome/razão social
                        4. SERVIÇOS: Descrição detalhada, código do serviço, alíquota ISS
                        5. VALORES: Valor bruto, deduções, valor líquido, ISS
                        6. IMPOSTOS MUNICIPAIS: ISS, ISSRF se houver
                        7. IMPOSTOS FEDERAIS: IR, INSS, CSLL, COFINS, PIS
                        
                        ATENÇÃO ESPECIAL:
                        - ISS (Imposto sobre Serviços) é o principal imposto
                        - Pode haver retenções na fonte (ISSRF, IR, INSS)
                        - Código do serviço (LC 116/2003)
                        - Alíquota de ISS varia por município
                        
                        Responda APENAS em JSON com foco em dados de serviços."""
                    },
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": "Extraia todos os dados deste documento de serviços:"
                            },
                            {
                                "type": "image_url",
                                "image_url": {"url": f"data:image/png;base64,{image_base64}"}
                            }
                        ]
                    }
                ],
                max_tokens=2000,
                temperature=0.05
            )
            
            return json.loads(response.choices[0].message.content)
            
        except Exception as e:
            self.logger.error(f"Service document extraction failed: {str(e)}")
            return {}
    
    def _extract_simplified_format(self, image_base64: str, layout_info: Dict) -> Dict[str, Any]:
        """Extract data from simplified formats (NFCe, etc.)."""
        try:
            response = self.client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {
                        "role": "system",
                        "content": """Você é especialista em NFCe e cupons fiscais eletrônicos.
                        
                        Este é um formato SIMPLIFICADO (NFCe/Cupom). Características:
                        - Layout compacto, similar a cupom de compra
                        - Dados essenciais apenas
                        - Foco no consumidor final
                        
                        EXTRAIA:
                        1. EMITENTE: CNPJ, nome fantasia, endereço resumido
                        2. IDENTIFICAÇÃO: Número NFCe, série, data/hora
                        3. PRODUTOS/SERVIÇOS: Lista simplificada
                        4. TOTAIS: Valor total, forma de pagamento
                        5. CHAVE DE ACESSO: Para consulta
                        6. QR CODE: Se visível, descreva
                        
                        Formato é mais simples, então alguns campos podem não existir.
                        
                        Responda APENAS em JSON adaptado ao formato simplificado."""
                    },
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": "Extraia dados deste documento simplificado:"
                            },
                            {
                                "type": "image_url",
                                "image_url": {"url": f"data:image/png;base64,{image_base64}"}
                            }
                        ]
                    }
                ],
                max_tokens=1500,
                temperature=0.05
            )
            
            return json.loads(response.choices[0].message.content)
            
        except Exception as e:
            self.logger.error(f"Simplified format extraction failed: {str(e)}")
            return {}
    
    def _extract_universal_fallback(self, image_base64: str, layout_info: Dict) -> Dict[str, Any]:
        """Universal fallback extraction for unknown or custom formats."""
        try:
            response = self.client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {
                        "role": "system",
                        "content": """Você é um extrator universal de documentos fiscais brasileiros.
                        
                        Este documento tem formato DESCONHECIDO ou PERSONALIZADO. 
                        Use estratégia de extração ADAPTATIVA:
                        
                        ABORDAGEM UNIVERSAL:
                        1. IDENTIFIQUE o tipo de documento analisando textos-chave
                        2. LOCALIZE campos por padrões (CNPJ: XX.XXX.XXX/XXXX-XX, etc.)
                        3. BUSQUE seções típicas: emitente, destinatário, valores, impostos
                        4. EXTRAIA o que for visível e identificável
                        5. ADAPTE a estrutura ao conteúdo encontrado
                        
                        PADRÕES A BUSCAR:
                        - CNPJ/CPF (formatação brasileira)
                        - Datas (DD/MM/AAAA ou DD/MM/AA HH:MM)
                        - Valores monetários (R$ X.XXX,XX)
                        - Códigos fiscais
                        - Endereços brasileiros (CEP, estados)
                        
                        SEJA FLEXÍVEL mas PRECISO. Se um campo não existe, use null.
                        Priorize QUALIDADE sobre quantidade de dados.
                        
                        Responda em JSON com a estrutura que melhor representa o documento."""
                    },
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": "Analise este documento fiscal de formato desconhecido e extraia todos os dados possíveis de forma adaptativa:"
                            },
                            {
                                "type": "image_url",
                                "image_url": {"url": f"data:image/png;base64,{image_base64}"}
                            }
                        ]
                    }
                ],
                max_tokens=2500,
                temperature=0.1  # Slightly higher for adaptability
            )
            
            return json.loads(response.choices[0].message.content)
            
        except Exception as e:
            self.logger.error(f"Universal fallback extraction failed: {str(e)}")
            return {}
    
    def _extract_items_universal(self, images: List[str], layout_info: Dict) -> List[Dict[str, Any]]:
        """Extract items using layout-aware strategy."""
        try:
            # Use first image for items extraction
            image_base64 = images[0]
            
            response = self.client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {
                        "role": "system",
                        "content": f"""Você é especialista em extração de ITENS de documentos fiscais.
                        
                        Layout detectado: {layout_info.get('layout_type', 'unknown')}
                        Complexidade: {layout_info.get('complexity', 'medium')}
                        
                        EXTRAIA TODOS OS ITENS/PRODUTOS/SERVIÇOS visíveis.
                        
                        Para cada item, capture:
                        - Código/referência
                        - Descrição completa
                        - Quantidade
                        - Unidade
                        - Valor unitário
                        - Valor total
                        - Códigos fiscais (NCM, CFOP, CST)
                        - Impostos por item (se visível)
                        
                        ADAPTE-SE AO FORMATO:
                        - Se tabela estruturada: extraia linha por linha
                        - Se lista simples: capture o disponível
                        - Se formato texto: identifique itens por separadores
                        
                        Responda APENAS em JSON como array de itens:
                        [
                            {{"codigo": "...", "descricao": "...", "quantidade": X, "valor_unitario": X, "valor_total": X, ...}},
                            ...
                        ]
                        
                        Se não houver itens, retorne array vazio: []"""
                    },
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": "Extraia todos os itens/produtos/serviços deste documento:"
                            },
                            {
                                "type": "image_url",
                                "image_url": {"url": f"data:image/png;base64,{image_base64}"}
                            }
                        ]
                    }
                ],
                max_tokens=3000,
                temperature=0.05
            )
            
            items_data = json.loads(response.choices[0].message.content)
            return items_data if isinstance(items_data, list) else []
            
        except Exception as e:
            self.logger.error(f"Items extraction failed: {str(e)}")
            return []
    
    def _extract_taxes_universal(self, images: List[str], layout_info: Dict, total_value: float) -> Dict[str, float]:
        """Extract taxes using format-aware processing."""
        try:
            # Use first image for tax extraction
            image_base64 = images[0]
            
            document_type = layout_info.get('document_type', 'NFe')
            
            response = self.client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {
                        "role": "system",
                        "content": f"""Você é especialista em impostos brasileiros.
                        
                        Documento: {document_type}
                        Layout: {layout_info.get('layout_type', 'unknown')}
                        
                        EXTRAIA TODOS OS IMPOSTOS visíveis com VALORES EXATOS.
                        
                        IMPOSTOS BRASILEIROS PRINCIPAIS:
                        - ICMS (estadual) - produtos
                        - IPI (federal) - produtos industrializados
                        - PIS (federal) - faturamento
                        - COFINS (federal) - faturamento
                        - ISS/ISSQN (municipal) - serviços
                        - IR (renda) - retenção na fonte
                        - INSS (previdência) - retenção
                        - CSLL (contribuição social)
                        - ISSRF (ISS retido na fonte)
                        
                        INSTRUÇÕES CRÍTICAS:
                        1. Leia valores EXATAMENTE como aparecem
                        2. Use vírgula decimal brasileira
                        3. Se valor não visível ou zero, use 0.0
                        4. NUNCA invente valores
                        5. Foque em áreas de impostos/tributos
                        
                        ADAPTE-SE AO TIPO:
                        - NFe: ICMS, IPI, PIS, COFINS principais
                        - NFSE: ISS, IR, INSS, CSLL principais
                        - NFCe: Impostos simplificados
                        
                        Responda APENAS em JSON:
                        {{
                            "valor_icms": 0.0,
                            "valor_ipi": 0.0,
                            "valor_pis": 0.0,
                            "valor_cofins": 0.0,
                            "valor_iss": 0.0,
                            "valor_ir": 0.0,
                            "valor_inss": 0.0,
                            "valor_csll": 0.0,
                            "valor_issrf": 0.0
                        }}"""
                    },
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": f"Extraia TODOS os impostos deste documento. Valor total para referência: R$ {total_value:,.2f}"
                            },
                            {
                                "type": "image_url",
                                "image_url": {"url": f"data:image/png;base64,{image_base64}"}
                            }
                        ]
                    }
                ],
                max_tokens=1000,
                temperature=0.05
            )
            
            tax_data = json.loads(response.choices[0].message.content)
            
            # Ensure all expected tax fields exist
            expected_fields = [
                'valor_icms', 'valor_ipi', 'valor_pis', 'valor_cofins',
                'valor_iss', 'valor_ir', 'valor_inss', 'valor_csll', 'valor_issrf'
            ]
            
            for field in expected_fields:
                if field not in tax_data:
                    tax_data[field] = 0.0
                    
            return tax_data
            
        except Exception as e:
            self.logger.error(f"Tax extraction failed: {str(e)}")
            return {
                'valor_icms': 0.0, 'valor_ipi': 0.0, 'valor_pis': 0.0,
                'valor_cofins': 0.0, 'valor_iss': 0.0, 'valor_ir': 0.0,
                'valor_inss': 0.0, 'valor_csll': 0.0, 'valor_issrf': 0.0
            }
    
    def _validate_and_consolidate(self, extracted_data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate and consolidate extracted data."""
        # Ensure required fields exist with defaults
        defaults = {
            'numero_nfe': None,
            'serie_nfe': None,
            'data_emissao': None,
            'chave_acesso': None,
            'emitente_cnpj': None,
            'emitente_razao_social': None,
            'destinatario_cnpj': None,
            'destinatario_nome': None,
            'valor_total_servicos': 0.0,
            'valor_total_produtos': 0.0,
            'base_calculo_icms': 0.0,
            'base_calculo_issqn': 0.0
        }
        
        # Merge with defaults
        for key, default_value in defaults.items():
            if key not in extracted_data or extracted_data[key] is None:
                extracted_data[key] = default_value
        
        # Clean and format values
        extracted_data = self._clean_extracted_values(extracted_data)
        
        return extracted_data
    
    def _clean_extracted_values(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Clean and format extracted values."""
        # Clean CNPJ/CPF
        if data.get('emitente_cnpj'):
            data['emitente_cnpj'] = self._clean_cnpj(data['emitente_cnpj'])
        if data.get('destinatario_cnpj'):
            data['destinatario_cnpj'] = self._clean_cnpj(data['destinatario_cnpj'])
        
        # Clean monetary values
        monetary_fields = [
            'valor_total_servicos', 'valor_total_produtos', 
            'base_calculo_icms', 'base_calculo_issqn'
        ]
        
        for field in monetary_fields:
            if field in data:
                data[field] = self._clean_monetary_value(data[field])
        
        return data
    
    def _clean_cnpj(self, cnpj: str) -> str:
        """Clean CNPJ format."""
        if not cnpj:
            return ""
        # Remove all non-digits and reformat if needed
        digits = ''.join(filter(str.isdigit, str(cnpj)))
        if len(digits) == 14:
            return f"{digits[:2]}.{digits[2:5]}.{digits[5:8]}/{digits[8:12]}-{digits[12:14]}"
        elif len(digits) == 11:  # CPF
            return f"{digits[:3]}.{digits[3:6]}.{digits[6:9]}-{digits[9:11]}"
        return cnpj
    
    def _clean_monetary_value(self, value) -> float:
        """Clean monetary value."""
        if value is None:
            return 0.0
        
        if isinstance(value, (int, float)):
            return float(value)
        
        if isinstance(value, str):
            # Remove currency symbols and convert
            cleaned = value.replace('R$', '').replace(' ', '')
            cleaned = cleaned.replace('.', '').replace(',', '.')
            try:
                return float(cleaned)
            except:
                return 0.0
        
        return 0.0


def process_pdf_universal(file_path: str) -> Dict[str, Any]:
    """
    Universal PDF processing function that handles any NFe format.
    
    Args:
        file_path (str): Path to the PDF file
        
    Returns:
        dict: Processing result with extracted data
    """
    processor = UniversalPDFProcessor()
    return processor.process_pdf_universal(file_path)