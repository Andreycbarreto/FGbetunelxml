"""
Universal PDF NFe Processor (Simplified)
Robust PDF processing system designed to handle ANY NFe PDF format
with intelligent layout detection and adaptive data extraction.
"""

import os
import base64
import logging
import json
from typing import Dict, Any, List, Optional
from openai import OpenAI
import pymupdf
from json_cleaner import clean_and_parse_json

logger = logging.getLogger(__name__)

class UniversalPDFSimple:
    """Universal PDF processor that adapts to any NFe format."""
    
    def __init__(self):
        self.client = OpenAI(
            api_key=os.environ.get("OPENAI_API_KEY"),
            timeout=90.0  # Extended timeout for complex processing
        )
        self.logger = logging.getLogger(__name__)
    
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
            
            # Step 3: Extract data using adaptive prompts based on layout
            extracted_data = self._extract_with_adaptive_strategy(pdf_images[0], layout_info)
            
            # Step 4: Extract items
            items_data = self._extract_items_adaptive(pdf_images[0], layout_info)
            extracted_data['items'] = items_data
            
            # Step 5: Extract taxes
            tax_data = self._extract_taxes_adaptive(pdf_images[0], layout_info, extracted_data.get('valor_total_servicos', 0))
            extracted_data.update(tax_data)
            
            # Step 6: Validate and clean data
            final_data = self._validate_and_clean(extracted_data)
            
            self.logger.info("Universal PDF processing completed successfully")
            return {
                'success': True,
                'data': final_data,
                'confidence_score': layout_info.get('confidence', 0.8),
                'processing_notes': [f"Layout detected: {layout_info.get('layout_type', 'universal')}"]
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
            
            for page_num in range(min(2, len(pdf_document))):  # Max 2 pages
                page = pdf_document[page_num]
                
                # Use high DPI for better OCR quality
                mat = pymupdf.Matrix(2.0, 2.0)  # 2x zoom for better quality
                pix = page.get_pixmap(matrix=mat, alpha=False)
                
                img_data = pix.tobytes("png")
                img_base64 = base64.b64encode(img_data).decode()
                images.append(img_base64)
            
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
                        
                        Analise esta imagem e identifique o tipo de documento:
                        
                        TIPOS POSSÍVEIS:
                        - danfe_portrait: DANFE vertical padrão
                        - danfe_landscape: DANFE horizontal  
                        - nfse_service: Documento de serviços (NFSE)
                        - nfce_receipt: NFCe ou cupom fiscal
                        - government: Formato de prefeitura
                        - custom: Formato personalizado
                        
                        Responda APENAS em formato JSON simples:
                        {
                            "layout_type": "tipo_detectado",
                            "document_type": "NFe|NFCe|NFSE",
                            "confidence": 0.8
                        }"""
                    },
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": "Identifique o tipo deste documento fiscal:"
                            },
                            {
                                "type": "image_url",
                                "image_url": {"url": f"data:image/png;base64,{image_base64}"}
                            }
                        ]
                    }
                ],
                max_tokens=500,
                temperature=0.1
            )
            
            content = response.choices[0].message.content
            fallback = {
                "layout_type": "custom",
                "document_type": "NFe", 
                "confidence": 0.5
            }
            return clean_and_parse_json(content, fallback)
            
        except Exception as e:
            self.logger.error(f"Layout detection failed: {str(e)}")
            return {
                "layout_type": "custom",
                "document_type": "NFe",
                "confidence": 0.5
            }
    
    def _extract_with_adaptive_strategy(self, image_base64: str, layout_info: Dict) -> Dict[str, Any]:
        """Extract data using strategy adapted to detected layout."""
        
        layout_type = layout_info.get('layout_type', 'custom')
        doc_type = layout_info.get('document_type', 'NFe')
        
        # Create adaptive prompt based on layout
        if 'service' in layout_type.lower() or doc_type == 'NFSE':
            prompt_focus = "serviços (ISS, retenções, código de serviço)"
        elif 'nfce' in layout_type.lower() or doc_type == 'NFCe':
            prompt_focus = "cupom fiscal simplificado"
        else:
            prompt_focus = "DANFE padrão (ICMS, IPI, produtos)"
        
        try:
            response = self.client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {
                        "role": "system",
                        "content": f"""Você é especialista em extração de dados de documentos fiscais brasileiros.

                        DOCUMENTO DETECTADO: {doc_type} - {layout_type}
                        FOCO: {prompt_focus}
                        
                        Extraia TODOS os dados visíveis deste documento fiscal:
                        
                        CAMPOS OBRIGATÓRIOS:
                        - numero_nfe, serie_nfe, data_emissao, chave_acesso
                        - emitente_cnpj, emitente_razao_social, emitente_endereco
                        - destinatario_cnpj, destinatario_nome, destinatario_endereco  
                        - valor_total_servicos, valor_total_produtos
                        - base_calculo_icms, base_calculo_issqn
                        
                        REGRAS CRÍTICAS:
                        1. Extraia valores EXATAMENTE como aparecem
                        2. Use formato brasileiro: vírgula decimal
                        3. CNPJ: XX.XXX.XXX/XXXX-XX
                        4. Datas: DD/MM/AAAA
                        5. Se não encontrar, use null ou 0.0
                        6. NUNCA invente dados
                        
                        Responda APENAS em JSON válido sem comentários."""
                    },
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": f"Extraia todos os dados deste documento {doc_type}:"
                            },
                            {
                                "type": "image_url", 
                                "image_url": {"url": f"data:image/png;base64,{image_base64}"}
                            }
                        ]
                    }
                ],
                max_tokens=2500,
                temperature=0.05
            )
            
            content = response.choices[0].message.content
            if content:
                try:
                    return json.loads(content)
                except json.JSONDecodeError:
                    self.logger.warning(f"Invalid JSON in data extraction: {content[:200]}")
                    return {}
            
            return {}
            
        except Exception as e:
            self.logger.error(f"Data extraction failed: {str(e)}")
            return {}
    
    def _extract_items_adaptive(self, image_base64: str, layout_info: Dict) -> List[Dict[str, Any]]:
        """Extract items using layout-aware strategy."""
        try:
            layout_type = layout_info.get('layout_type', 'custom')
            
            if 'service' in layout_type.lower():
                item_prompt = "serviços prestados com códigos de serviço"
            else:
                item_prompt = "produtos/mercadorias com NCM e CFOP"
            
            response = self.client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {
                        "role": "system",
                        "content": f"""Você é especialista em extração de ITENS de documentos fiscais.
                        
                        Layout: {layout_type}
                        Foco: {item_prompt}
                        
                        Extraia TODOS os itens/produtos/serviços visíveis:
                        
                        Para cada item:
                        - codigo: código/referência
                        - descricao: descrição completa
                        - quantidade: quantidade
                        - unidade: unidade (UN, KG, etc)
                        - valor_unitario: valor unitário
                        - valor_total: valor total do item
                        - ncm: código NCM (se produto)
                        - cfop: CFOP
                        - cst: CST/CSOSN
                        
                        REGRAS:
                        1. Analise tabelas de itens cuidadosamente
                        2. Preserve formatação de valores brasileira
                        3. Se não houver itens, retorne array vazio
                        4. Não invente dados
                        
                        Responda APENAS em JSON como array:
                        [
                            {{"codigo": "...", "descricao": "...", "quantidade": 1, "valor_unitario": 100.50, "valor_total": 100.50}},
                            ...
                        ]
                        
                        Se não houver itens: []"""
                    },
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": "Extraia todos os itens deste documento:"
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
            
            content = response.choices[0].message.content
            if content:
                try:
                    items = json.loads(content)
                    return items if isinstance(items, list) else []
                except json.JSONDecodeError:
                    self.logger.warning(f"Invalid JSON in items extraction: {content[:200]}")
                    return []
            
            return []
            
        except Exception as e:
            self.logger.error(f"Items extraction failed: {str(e)}")
            return []
    
    def _extract_taxes_adaptive(self, image_base64: str, layout_info: Dict, total_value: float) -> Dict[str, float]:
        """Extract taxes using format-aware processing."""
        try:
            layout_type = layout_info.get('layout_type', 'custom')
            doc_type = layout_info.get('document_type', 'NFe')
            
            if 'service' in layout_type.lower() or doc_type == 'NFSE':
                tax_focus = "ISS, IR, INSS, CSLL, COFINS, PIS (impostos de serviços)"
            else:
                tax_focus = "ICMS, IPI, PIS, COFINS (impostos de produtos)"
            
            response = self.client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {
                        "role": "system",
                        "content": f"""Você é especialista em impostos brasileiros.
                        
                        Documento: {doc_type}
                        Layout: {layout_type}
                        Foco: {tax_focus}
                        
                        Extraia TODOS os impostos visíveis com valores EXATOS:
                        
                        IMPOSTOS BRASILEIROS:
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
                        2. Use vírgula decimal brasileira convertida para ponto
                        3. Se não encontrar, use 0.0
                        4. NUNCA invente valores
                        5. Foque em tabelas/seções de impostos
                        
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
                                "text": f"Extraia todos os impostos. Valor total de referência: R$ {total_value:,.2f}"
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
            
            content = response.choices[0].message.content
            if content:
                try:
                    tax_data = json.loads(content)
                    # Ensure all expected fields exist
                    expected_fields = [
                        'valor_icms', 'valor_ipi', 'valor_pis', 'valor_cofins',
                        'valor_iss', 'valor_ir', 'valor_inss', 'valor_csll', 'valor_issrf'
                    ]
                    
                    for field in expected_fields:
                        if field not in tax_data:
                            tax_data[field] = 0.0
                            
                    return tax_data
                except json.JSONDecodeError:
                    self.logger.warning(f"Invalid JSON in tax extraction: {content[:200]}")
            
            # Return zero taxes as fallback
            return {
                'valor_icms': 0.0, 'valor_ipi': 0.0, 'valor_pis': 0.0,
                'valor_cofins': 0.0, 'valor_iss': 0.0, 'valor_ir': 0.0,
                'valor_inss': 0.0, 'valor_csll': 0.0, 'valor_issrf': 0.0
            }
            
        except Exception as e:
            self.logger.error(f"Tax extraction failed: {str(e)}")
            return {
                'valor_icms': 0.0, 'valor_ipi': 0.0, 'valor_pis': 0.0,
                'valor_cofins': 0.0, 'valor_iss': 0.0, 'valor_ir': 0.0,
                'valor_inss': 0.0, 'valor_csll': 0.0, 'valor_issrf': 0.0
            }
    
    def _validate_and_clean(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate and clean extracted data."""
        # Ensure required fields exist
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
        
        # Apply defaults
        for key, default_value in defaults.items():
            if key not in data or data[key] is None:
                data[key] = default_value
        
        # Clean CNPJ fields
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
        
        # Remove all non-digits
        digits = ''.join(filter(str.isdigit, str(cnpj)))
        
        if len(digits) == 14:  # CNPJ
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
            # Remove currency symbols and convert Brazilian format
            cleaned = value.replace('R$', '').replace(' ', '')
            cleaned = cleaned.replace('.', '').replace(',', '.')
            try:
                return float(cleaned)
            except:
                return 0.0
        
        return 0.0


def process_pdf_universal_simple(file_path: str) -> Dict[str, Any]:
    """
    Universal PDF processing function that handles any NFe format.
    
    Args:
        file_path (str): Path to the PDF file
        
    Returns:
        dict: Processing result with extracted data
    """
    processor = UniversalPDFSimple()
    return processor.process_pdf_universal(file_path)