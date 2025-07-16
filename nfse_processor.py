"""
NFS-e Specialized Processor
Processador especializado para documentos NFS-e (Nota Fiscal de Serviços Eletrônica)
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

class NFSeProcessor:
    """Processador especializado para documentos NFS-e"""
    
    def __init__(self):
        self.client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
        self.logger = logging.getLogger(__name__)
        
    def detect_nfse_format(self, text_content: str) -> bool:
        """Detecta se o documento é uma NFS-e"""
        nfse_indicators = [
            "NFS-e",
            "NOTA FISCAL DE SERVIÇOS ELETRÔNICA",
            "Nota Fiscal de Serviços",
            "DESCRIÇÃO DOS SERVIÇOS",
            "ISSQN",
            "IR RETIDO",
            "INSS RETIDO",
            "PIS RETIDO",
            "COFINS RETIDO",
            "CSLL RETIDO",
            "VALOR LÍQUIDO",
            "PRESTADOR DE SERVIÇOS",
            "TOMADOR DE SERVIÇOS",
            "RETENÇÕES FEDERAIS"
        ]
        
        text_upper = text_content.upper()
        indicators_found = sum(1 for indicator in nfse_indicators if indicator in text_upper)
        
        self.logger.info(f"NFS-e indicators found: {indicators_found}/12")
        return indicators_found >= 6
    
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
    
    def extract_nfse_data_with_vision(self, base64_image: str) -> Dict[str, Any]:
        """Extrai dados da NFS-e usando GPT-4 Vision com prompt especializado"""
        
        nfse_prompt = """
Você é um especialista em documentos fiscais brasileiros. Analise esta NFS-e (Nota Fiscal de Serviços Eletrônica) e extraia TODOS os dados visíveis com precisão absoluta.

INSTRUÇÕES CRÍTICAS:
1. Leia EXATAMENTE o que está escrito no documento
2. NÃO invente valores - se não conseguir ler, use campo vazio ou 0
3. Mantenha formatação brasileira para valores monetários
4. Extraia dados de TODAS as seções visíveis

SEÇÕES OBRIGATÓRIAS DA NFS-e:

**CABEÇALHO E IDENTIFICAÇÃO:**
- Número da NFS-e
- Série (se presente)
- Data de Emissão (procure por "Data de Emissão", "DT. EMISSÃO", "EMISSÃO" - formato dd/mm/yyyy)
- Competência (mês/ano)
- Código de Verificação

ATENÇÃO ESPECIAL PARA DATAS:
- A Data de Emissão está sempre no cabeçalho do documento
- Pode aparecer como "Data de Emissão:", "DT. EMISSÃO:", ou "EMISSÃO:"
- Sempre no formato brasileiro: dd/mm/yyyy (exemplo: 15/03/2024)
- Leia com cuidado para não confundir com outros números
- Se não conseguir ler claramente, deixe vazio ""

**PRESTADOR DE SERVIÇOS:**
- Razão Social
- CNPJ
- Inscrição Municipal
- Endereço completo
- CEP, Município, UF

**TOMADOR DE SERVIÇOS:**
- Nome/Razão Social
- CNPJ/CPF
- Endereço completo
- CEP, Município, UF

**DESCRIÇÃO DOS SERVIÇOS:**
- Código do Serviço (ex: 01.01, 14.05)
- Código de Atividade (CNAE)
- Descrição detalhada dos serviços
- Local da Prestação do Serviço
- Valor dos Serviços

**CÁLCULO DOS IMPOSTOS (seção crítica):**
- Valor Total dos Serviços
- (-) Deduções (se houver)
- (=) Base de Cálculo
- Alíquota ISSQN (%)
- Valor do ISSQN
- IR Retido (Imposto de Renda)
- INSS Retido
- PIS Retido
- COFINS Retido
- CSLL Retido (Contribuição Social sobre Lucro Líquido)
- Outras Retenções
- Valor Líquido

**VALORES ADICIONAIS:**
- Desconto Incondicional
- Desconto Condicional
- Valor ISS
- Outras Informações

Responda APENAS em JSON válido com esta estrutura exata:

{
  "numero_nfse": "string",
  "serie": "string",
  "data_emissao": "dd/mm/yyyy",
  "competencia": "mm/yyyy",
  "codigo_verificacao": "string",
  
  "prestador_razao_social": "string",
  "prestador_cnpj": "string",
  "prestador_inscricao_municipal": "string",
  "prestador_endereco": "string",
  "prestador_cep": "string",
  "prestador_municipio": "string",
  "prestador_uf": "string",
  
  "tomador_nome": "string",
  "tomador_cnpj": "string",
  "tomador_endereco": "string",
  "tomador_cep": "string",
  "tomador_municipio": "string",
  "tomador_uf": "string",
  
  "codigo_servico": "string",
  "codigo_atividade": "string",
  "descricao_servicos": "string",
  "local_prestacao": "string",
  
  "valor_servicos": 0.00,
  "valor_deducoes": 0.00,
  "base_calculo": 0.00,
  "aliquota_issqn": 0.00,
  "valor_issqn": 0.00,
  "valor_ir": 0.00,
  "valor_inss": 0.00,
  "valor_pis": 0.00,
  "valor_cofins": 0.00,
  "valor_csll": 0.00,
  "outras_retencoes": 0.00,
  "valor_liquido": 0.00,
  "desconto_incondicional": 0.00,
  "desconto_condicional": 0.00,
  "valor_iss": 0.00,
  "outras_informacoes": "string"
}

IMPORTANTE: 
- Foque especialmente na seção de impostos e retenções
- Identifique corretamente IR, INSS, PIS, COFINS, CSLL
- Extraia os valores exatos que estão visíveis no documento
- Para códigos de serviço, mantenha formato XX.XX (ex: 01.01, 14.05)
"""

        try:
            response = self.client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": nfse_prompt},
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
            self.logger.error(f"Error in NFS-e vision extraction: {e}")
            return {}
    
    def enhance_date_extraction(self, raw_data: Dict[str, Any], text_content: str, base64_image: str = None) -> Dict[str, Any]:
        """Melhora a extração de datas usando validação aprimorada"""
        
        # Validar e corrigir data de emissão
        emission_date = raw_data.get('data_emissao', '')
        
        # Se não encontrou data na extração principal, tenta métodos especializados
        if not emission_date or emission_date == '':
            self.logger.info("Emission date not found in main extraction, trying specialized methods")
            
            # Método 1: Extrator especializado de data de emissão (mais eficaz)
            if base64_image:
                try:
                    from emission_date_extractor import EmissionDateExtractor
                    specialized_extractor = EmissionDateExtractor()
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
                if base64_image:
                    try:
                        from emission_date_extractor import EmissionDateExtractor
                        specialized_extractor = EmissionDateExtractor()
                        fallback_date = specialized_extractor.extract_emission_date_only(base64_image)
                        if fallback_date:
                            emission_date = fallback_date
                            self.logger.info(f"Fallback to specialized extractor: {emission_date}")
                    except Exception as e:
                        self.logger.warning(f"Fallback specialized extractor failed: {e}")
        
        # Atualizar dados com datas corrigidas
        raw_data['data_emissao'] = emission_date or ''
        
        return raw_data

    def normalize_nfse_data(self, raw_data: Dict[str, Any]) -> Dict[str, Any]:
        """Normaliza dados da NFS-e para formato do banco de dados"""
        
        # Mapeamento específico para campos NFS-e -> Database
        normalized = {
            # Identificação do documento
            'numero_nf': raw_data.get('numero_nfse', ''),
            'serie': raw_data.get('serie', ''),
            'data_emissao': raw_data.get('data_emissao', ''),
            'codigo_verificacao': raw_data.get('codigo_verificacao', ''),
            
            # Prestador (emitente na NFS-e)
            'razao_social_emitente': raw_data.get('prestador_razao_social', ''),
            'cnpj_emitente': raw_data.get('prestador_cnpj', ''),
            'endereco_emitente': raw_data.get('prestador_endereco', ''),
            'inscricao_municipal_emitente': raw_data.get('prestador_inscricao_municipal', ''),
            'emitente_cep': raw_data.get('prestador_cep', ''),
            'emitente_municipio': raw_data.get('prestador_municipio', ''),
            'emitente_uf': raw_data.get('prestador_uf', ''),
            
            # Tomador (destinatário na NFS-e)
            'destinatario_nome': raw_data.get('tomador_nome', ''),
            'destinatario_cnpj': raw_data.get('tomador_cnpj', ''),
            'destinatario_endereco': raw_data.get('tomador_endereco', ''),
            'destinatario_cep': raw_data.get('tomador_cep', ''),
            'destinatario_municipio': raw_data.get('tomador_municipio', ''),
            'destinatario_uf': raw_data.get('tomador_uf', ''),
            
            # Serviços
            'codigo_servico': raw_data.get('codigo_servico', ''),
            'codigo_atividade': raw_data.get('codigo_atividade', ''),
            'descricao_servico': raw_data.get('descricao_servicos', ''),
            'local_prestacao_servico': raw_data.get('local_prestacao', ''),
            
            # Valores principais
            'valor_total_servicos': self._parse_decimal(raw_data.get('valor_servicos', 0)),
            'valor_total_nf': self._parse_decimal(raw_data.get('valor_liquido', 0)),
            'base_calculo_issqn': self._parse_decimal(raw_data.get('base_calculo', 0)),
            'valor_deducoes': self._parse_decimal(raw_data.get('valor_deducoes', 0)),
            'valor_desconto': self._parse_decimal(raw_data.get('desconto_incondicional', 0)) + self._parse_decimal(raw_data.get('desconto_condicional', 0)),
            
            # Impostos e retenções (campos principais da NFS-e)
            'valor_issqn': self._parse_decimal(raw_data.get('valor_issqn', 0)),
            'valor_ir': self._parse_decimal(raw_data.get('valor_ir', 0)),
            'valor_inss': self._parse_decimal(raw_data.get('valor_inss', 0)),
            'valor_pis': self._parse_decimal(raw_data.get('valor_pis', 0)),
            'valor_cofins': self._parse_decimal(raw_data.get('valor_cofins', 0)),
            'valor_csll': self._parse_decimal(raw_data.get('valor_csll', 0)),
            'outras_retencoes': self._parse_decimal(raw_data.get('outras_retencoes', 0)),
            'aliquota_issqn': self._parse_decimal(raw_data.get('aliquota_issqn', 0)),
            
            # Informações adicionais
            'informacoes_adicionais': raw_data.get('outras_informacoes', ''),
            'competencia': raw_data.get('competencia', ''),
            
            # Items (NFS-e geralmente tem um serviço principal)
            'items': [{
                'codigo_servico': raw_data.get('codigo_servico', ''),
                'codigo_atividade': raw_data.get('codigo_atividade', ''),
                'descricao_servico': raw_data.get('descricao_servicos', ''),
                'servico_local_prestacao': raw_data.get('local_prestacao', ''),
                'servico_valor': self._parse_decimal(raw_data.get('valor_servicos', 0)),
                'servico_aliquota': self._parse_decimal(raw_data.get('aliquota_issqn', 0)),
                'tax_ir': self._parse_decimal(raw_data.get('valor_ir', 0)),
                'tax_inss': self._parse_decimal(raw_data.get('valor_inss', 0)),
                'tax_pis': self._parse_decimal(raw_data.get('valor_pis', 0)),
                'tax_cofins': self._parse_decimal(raw_data.get('valor_cofins', 0)),
                'tax_csll': self._parse_decimal(raw_data.get('valor_csll', 0)),
                'tax_issqn': self._parse_decimal(raw_data.get('valor_issqn', 0)),
                'tax_base_calculo': self._parse_decimal(raw_data.get('base_calculo', 0)),
                'tax_outras_retencoes': self._parse_decimal(raw_data.get('outras_retencoes', 0)),
                'unidade_comercial': 'UN',
                'quantidade_comercial': 1.0,
                'valor_unitario_comercial': self._parse_decimal(raw_data.get('valor_servicos', 0)),
                'valor_total_produto': self._parse_decimal(raw_data.get('valor_servicos', 0))
            }] if raw_data.get('descricao_servicos') else []
        }
        
        # Aplicar limpeza de datas
        normalized = clean_date_fields(normalized)
        
        return normalized
    
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
    
    def process_nfse_pdf(self, pdf_path: str, original_filename: str) -> Dict[str, Any]:
        """Processa um PDF NFS-e completo"""
        
        self.logger.info(f"Starting NFS-e processing for {original_filename}")
        
        try:
            # Converter PDF para imagens
            images = self.convert_pdf_to_images(pdf_path)
            if not images:
                return {'success': False, 'error': 'Could not convert PDF to images'}
            
            # Processar primeira página (NFS-e geralmente é 1 página)
            base64_image = images[0]
            
            # Extrair texto para validação de datas
            doc = fitz.open(pdf_path)
            text_content = ""
            for page in doc:
                text_content += page.get_text()
            doc.close()
            
            # Extrair dados com GPT-4 Vision
            raw_data = self.extract_nfse_data_with_vision(base64_image)
            
            if not raw_data:
                return {'success': False, 'error': 'Could not extract data from NFS-e'}
            
            # Melhorar extração de datas com validação
            raw_data = self.enhance_date_extraction(raw_data, text_content, base64_image)
            
            # Normalizar dados
            normalized_data = self.normalize_nfse_data(raw_data)
            
            # Classificar tipo de operação
            try:
                from document_type_classifier import classify_document_operation_type
                operation_type = classify_document_operation_type(base64_image, normalized_data)
                normalized_data['tipo_operacao'] = operation_type
                self.logger.info(f"NFS-e classified as: {operation_type}")
            except Exception as e:
                self.logger.warning(f"Operation type classification failed: {e}")
                normalized_data['tipo_operacao'] = "Serviços e Produtos"
            
            self.logger.info(f"NFS-e processing successful for {original_filename}")
            self.logger.info(f"Extracted fields: {list(normalized_data.keys())}")
            
            return {
                'success': True,
                'data': normalized_data,
                'confidence_score': 0.95,  # Alto para processador especializado
                'processing_notes': [f'NFS-e processing with specialized extractor'],
                'document_format': 'NFS-e'
            }
            
        except Exception as e:
            self.logger.error(f"Error processing NFS-e {original_filename}: {e}")
            return {'success': False, 'error': str(e)}


def process_nfse_pdf(pdf_path: str, original_filename: str) -> Dict[str, Any]:
    """
    Função principal para processar PDFs NFS-e
    
    Args:
        pdf_path: Caminho para o arquivo PDF
        original_filename: Nome original do arquivo
        
    Returns:
        Resultado do processamento
    """
    processor = NFSeProcessor()
    return processor.process_nfse_pdf(pdf_path, original_filename)


def detect_if_nfse(pdf_path: str) -> bool:
    """
    Detecta se um PDF é uma NFS-e
    
    Args:
        pdf_path: Caminho para o arquivo PDF
        
    Returns:
        True se for NFS-e, False caso contrário
    """
    try:
        doc = fitz.open(pdf_path)
        text_content = ""
        for page_num in range(min(2, len(doc))):  # Primeiras 2 páginas
            page = doc[page_num]
            text_content += page.get_text()
        doc.close()
        
        processor = NFSeProcessor()
        return processor.detect_nfse_format(text_content)
    except:
        return False