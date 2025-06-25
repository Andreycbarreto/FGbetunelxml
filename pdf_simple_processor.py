"""
Simple PDF NFe Processor
A simplified version for processing NFe PDF files using OpenAI directly.
"""

import os
import logging
import pymupdf4llm
from typing import Dict, Any
from openai import OpenAI

logger = logging.getLogger(__name__)

class SimplePDFProcessor:
    """Simple processor for NFe PDF files."""
    
    def __init__(self):
        self.client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
        self.logger = logging.getLogger(__name__)
    
    def process_pdf_to_nfe_data(self, file_path: str) -> Dict[str, Any]:
        """
        Process a PDF file and extract NFe data using AI.
        
        Args:
            file_path (str): Path to the PDF file
            
        Returns:
            dict: Extracted NFe data or error information
        """
        try:
            self.logger.info(f"Starting simple PDF processing for: {file_path}")
            
            # Extract markdown from PDF
            markdown_content = pymupdf4llm.to_markdown(
                file_path,
                page_chunks=False,
                write_images=False,
                embed_images=False,
                show_progress=False
            )
            
            if not markdown_content or len(markdown_content.strip()) < 100:
                raise Exception("PDF content too short or empty")
            
            # Process with OpenAI directly
            nfe_data = self._extract_nfe_data_with_ai(markdown_content)
            
            return {
                'success': True,
                'data': nfe_data,
                'confidence_score': 0.85,
                'processing_notes': ['PDF processed successfully with OpenAI'],
                'markdown_content': markdown_content[:2000]  # Store first 2000 chars
            }
            
        except Exception as e:
            self.logger.error(f"Error processing PDF {file_path}: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'data': None,
                'confidence_score': 0.0,
                'processing_notes': [f'Error: {str(e)}']
            }
    
    def _extract_nfe_data_with_ai(self, markdown_content: str) -> Dict[str, Any]:
        """Extract NFe data using OpenAI."""
        
        prompt = f"""
        Você é um especialista em extrair dados de NFe brasileira. 
        Extraia todos os dados estruturados do conteúdo markdown de uma NFe em PDF.

        CONTEÚDO DO PDF (MARKDOWN):
        {markdown_content[:6000]}

        Extraia os seguintes dados (use null para campos não encontrados):

        {{
            "chave_nfe": "chave de acesso da NFe (44 dígitos)",
            "numero_nf": "número da nota fiscal",
            "serie": "série da nota",
            "modelo": "modelo do documento",
            "data_emissao": "data de emissão (formato YYYY-MM-DD)",
            "natureza_operacao": "natureza da operação",
            
            "emitente_cnpj": "CNPJ do emitente",
            "emitente_nome": "razão social do emitente",
            "emitente_fantasia": "nome fantasia",
            "emitente_endereco": "endereço completo",
            "emitente_municipio": "município",
            "emitente_uf": "UF",
            "emitente_cep": "CEP",
            
            "destinatario_cnpj": "CNPJ/CPF do destinatário",
            "destinatario_nome": "nome/razão social",
            "destinatario_endereco": "endereço completo",
            "destinatario_municipio": "município",
            "destinatario_uf": "UF",
            "destinatario_cep": "CEP",
            
            "valor_total_produtos": "valor total dos produtos (número)",
            "valor_total_nf": "valor total da nota (número)",
            "valor_icms": "valor do ICMS (número)",
            "valor_ipi": "valor do IPI (número)",
            "valor_pis": "valor do PIS (número)",
            "valor_cofins": "valor do COFINS (número)",
            
            "protocolo_autorizacao": "protocolo de autorização",
            "ambiente": "produção ou homologação",
            
            "items": [
                {{
                    "numero_item": "número do item",
                    "codigo_produto": "código do produto",
                    "descricao_produto": "descrição",
                    "quantidade_comercial": "quantidade (número)",
                    "valor_unitario_comercial": "valor unitário (número)",
                    "valor_total_produto": "valor total (número)"
                }}
            ]
        }}

        Responda APENAS em formato JSON válido. Use valores null para campos não encontrados.
        """
        
        try:
            response = self.client.chat.completions.create(
                model="gpt-4o",
                messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"},
                temperature=0.1,
                max_tokens=4000
            )
            
            content = response.choices[0].message.content
            if not content:
                raise ValueError("No content returned from OpenAI")
                
            import json
            extracted_data = json.loads(content)
            
            # Ensure items is a list
            if 'items' not in extracted_data:
                extracted_data['items'] = []
            elif not isinstance(extracted_data['items'], list):
                extracted_data['items'] = []
            
            return extracted_data
            
        except Exception as e:
            self.logger.error(f"Error extracting data with AI: {str(e)}")
            return {
                'chave_nfe': None,
                'numero_nf': None,
                'emitente_nome': 'Erro na extração',
                'destinatario_nome': 'Erro na extração',
                'valor_total_nf': 0.0,
                'items': []
            }