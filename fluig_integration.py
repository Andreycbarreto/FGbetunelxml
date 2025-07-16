"""
Fluig Integration Module
Handles integration with Fluig system for NFe processing
"""

import requests
from requests_oauthlib import OAuth1
import json
import logging
from datetime import datetime
from models import UserSettings, NFERecord, Empresa, Filial
from app import db
import os


class FluigIntegration:
    """Classe para integração com o sistema Fluig"""
    
    def __init__(self, user_settings):
        """
        Inicializa a integração com as configurações do usuário
        
        Args:
            user_settings: Instância de UserSettings com as credenciais
        """
        self.user_settings = user_settings
        self.auth = OAuth1(
            user_settings.consumer_key,
            user_settings.consumer_secret,
            user_settings.token_key,
            user_settings.token_secret
        )
        self.fluig_url = user_settings.fluig_url
        self.ged_folder_id = user_settings.ged_folder_id
        
    def upload_file_to_fluig(self, file_path, file_name):
        """
        Faz upload de um arquivo para o Fluig
        
        Args:
            file_path: Caminho do arquivo
            file_name: Nome do arquivo
            
        Returns:
            str: Nome do arquivo enviado
        """
        try:
            with open(file_path, 'rb') as f:
                files = {'file': (file_name, f)}
                logging.info(f"Enviando arquivo {file_name} para o Fluig...")
                
                upload_resp = requests.post(
                    f'{self.fluig_url}/ecm/upload',
                    files=files,
                    data={"isPublic": "false", "chunked": "false"},
                    auth=self.auth
                )
                upload_resp.raise_for_status()
                uploaded_file_name = upload_resp.json()['files'][0]['name']
                logging.info(f"Arquivo enviado com sucesso: {uploaded_file_name}")
                return uploaded_file_name
                
        except Exception as e:
            logging.error(f"Erro ao enviar arquivo para o Fluig: {str(e)}")
            raise
    
    def create_document_in_ged(self, uploaded_file_name):
        """
        Cria um documento no GED do Fluig
        
        Args:
            uploaded_file_name: Nome do arquivo enviado
            
        Returns:
            str: ID do documento criado
        """
        try:
            create_doc_payload = {
                "description": f"{uploaded_file_name} - Enviado via API",
                "parentId": int(self.ged_folder_id),
                "attachments": [{"fileName": uploaded_file_name}],
                "documentTypeId": 7,  # Essencial para aparecer na aba de anexos
                "formData": [
                    {
                        "name": "ecm-widgetpartgeneralinformation-utilizaVisualizadorInterno",
                        "value": False
                    }
                ]
            }
            
            logging.info("Criando documento no GED...")
            create_doc_resp = requests.post(
                f'{self.fluig_url}/api/public/ecm/document/createDocument',
                json=create_doc_payload,
                auth=self.auth
            )
            create_doc_resp.raise_for_status()
            attachment_id = create_doc_resp.json()['content']['id']
            logging.info(f"Documento criado com ID: {attachment_id}")
            return str(attachment_id)
            
        except Exception as e:
            logging.error(f"Erro ao criar documento no GED: {str(e)}")
            raise
    
    def start_transport_process(self, nfe_record, attachment_id):
        """
        Inicia processo de Importação de Frete para documentos CT-e
        
        Args:
            nfe_record: Registro NFE
            attachment_id: ID do documento no GED
            
        Returns:
            str: ID do processo criado
        """
        try:
            # Buscar dados da empresa e filial
            empresa = Empresa.query.filter_by(
                user_id=nfe_record.user_id,
                cnpj=nfe_record.cnpj_emitente.replace('.', '').replace('/', '').replace('-', '')
            ).first()
            
            filial = None
            if empresa:
                filial = Filial.query.filter_by(
                    user_id=nfe_record.user_id,
                    coligada=empresa.numero,
                    cnpj_filial=nfe_record.cnpj_emitente.replace('.', '').replace('/', '').replace('-', '')
                ).first()
            
            # Montar identificador
            identificador = f"Empresa: {empresa.nome_fantasia if empresa else 'N/A'} " \
                          f"Fornecedor: {nfe_record.cnpj_emitente} - {nfe_record.nome_emitente} " \
                          f"Numero: {nfe_record.numero_nfe} " \
                          f"Valor: {nfe_record.valor_total_nfe or 0:.2f} " \
                          f"Data de Vencimento: {nfe_record.data_vencimento.strftime('%d/%m/%Y') if nfe_record.data_vencimento else 'N/A'}"
            
            form_fields = {
                "identificador": identificador,
                "formSalvo": "",
                "dt_lanc": datetime.now().strftime('%d/%m/%Y'),
                "aprovadoN1": "",
                "aprovadoN2": "",
                "aprovadoN1_impXML": "",
                "indexTblItens": "",
                "indexesTblItens": "1",
                "atividadeConjunta": "",
                "cod_item": "01.071.003",  # Código padrão, pode ser customizado
                "nome_aprovador": "",
                "NOME_FORNECEDOR": nfe_record.nome_emitente or "",
                "numAtiv": "224",
                "numProc": "731485",
                "boletoAnexado": "",
                "prazo": "",
                "chave_acesso": nfe_record.chave_acesso or "",
                "tpDocXML": "CTE",
                "tpFreteXML": "2",
                "uniMedXML": "T",
                "aliqICMSXML": f"{nfe_record.aliquota_icms or 0:.2f}",
                "vlICMSXML": f"{nfe_record.valor_icms or 0:.2f}",
                "idNatXML": "21735",
                "idMov": "1760807",
                "codETDColetaXML": "SP",
                "codMUNColetaXML": "48500",
                "codETDEntregaXML": "MT",
                "codMUNEntregaXML": "03403",
                "tipoRemetenteXML": "C",
                "tipoDestinatarioXML": "C",
                "codTranspXML": "41432",
                "vlPedagioXML": "0,00",
                "produtoXML": nfe_record.descricao_produto or "",
                "chaveNFE": nfe_record.chave_acesso or "",
                "dtSaidaXML": nfe_record.data_emissao.strftime('%d/%m/%Y') if nfe_record.data_emissao else "",
                "fretePorContaXML": "2",
                "importadoXML": "S",
                "localEstoqueXML": "ALM",
                "baseCreditoXML": "03",
                "mat_colaborador": "034b12177b5511eb8a330a5864606cd7",
                "CIF_FOB_OUTROS": "S",
                "FRETE_INTERCOMPANY_FORN_TERC": "S",
                "destinacao_clone": "FOB",
                "codigoItem___1": "01.071.003",
                "nomeItem___1": nfe_record.descricao_produto or "",
                "quantidade___1": "1",
                "valorUnitario___1": f"{nfe_record.valor_total_nfe or 0:.2f}".replace('.', ','),
                "valorTotalItem___1": f"{nfe_record.valor_total_nfe or 0:.2f}".replace('.', ','),
                "documento_ged": attachment_id
            }
            
            start_process_payload = {
                "targetState": 128,
                "targetAssignee": "",
                "subProcessTargetState": 0,
                "comment": "Iniciado via API",
                "formFields": form_fields
            }
            
            logging.info("Iniciando processo de Importação de Frete...")
            start_proc_resp = requests.post(
                f'{self.fluig_url}/process-management/api/v2/processes/Importa%C3%A7%C3%A3o%20de%20Frete/start',
                json=start_process_payload,
                auth=self.auth
            )
            start_proc_resp.raise_for_status()
            process_instance_id = start_proc_resp.json()["processInstanceId"]
            logging.info(f"Processo de frete criado! ID: {process_instance_id}")
            return process_instance_id
            
        except Exception as e:
            logging.error(f"Erro ao iniciar processo de frete: {str(e)}")
            raise
    
    def start_service_process(self, nfe_record, attachment_id):
        """
        Inicia processo de Lançamento de Nota Fiscal para documentos de serviços
        
        Args:
            nfe_record: Registro NFE
            attachment_id: ID do documento no GED
            
        Returns:
            str: ID do processo criado
        """
        try:
            # Buscar dados da empresa e filial
            empresa = Empresa.query.filter_by(
                user_id=nfe_record.user_id,
                cnpj=nfe_record.cnpj_emitente.replace('.', '').replace('/', '').replace('-', '')
            ).first()
            
            filial = None
            if empresa:
                filial = Filial.query.filter_by(
                    user_id=nfe_record.user_id,
                    coligada=empresa.numero,
                    cnpj_filial=nfe_record.cnpj_emitente.replace('.', '').replace('/', '').replace('-', '')
                ).first()
            
            # Montar identificador
            identificador = f"Empresa: {empresa.nome_fantasia if empresa else 'N/A'} " \
                          f"Fornecedor: {nfe_record.nome_emitente} - {nfe_record.cnpj_emitente} " \
                          f"Numero: {nfe_record.numero_nfe} " \
                          f"Valor: {nfe_record.valor_total_nfe or 0:.2f} " \
                          f"Data de Vencimento: {nfe_record.data_vencimento.strftime('%d/%m/%Y') if nfe_record.data_vencimento else 'N/A'} " \
                          f"Forma de Pagamento: {nfe_record.forma_pagamento or 'N/A'}"
            
            form_fields = {
                "nome": "Sistema Automatizado",
                "matricula": "sistema",
                "email": "sistema@betunel.com.br",
                "Hdt_entrada_nf": datetime.now().strftime('%d/%m/%Y'),
                "dt_entrada_nf": datetime.now().strftime('%d/%m/%Y'),
                "nm_empresa": empresa.nome_fantasia if empresa else "N/A",
                "cod_empresa": str(empresa.numero) if empresa else "1",
                "cnpj": nfe_record.cnpj_emitente or "",
                "nm_filial": filial.nome_filial if filial else "N/A",
                "cod_filial": str(filial.filial) if filial else "1",
                "cnpj_filial": nfe_record.cnpj_emitente or "",
                "unid_negoc": "SUPPLY E CUSTOS",
                "cod_un": "0.10.02.01.001",
                "centro_custo": "1.0.3299 - SUPRIMENTOS",
                "cod_cc": "1.0.3299",
                "tp_doc": "Nota fiscal de serviço eletrônica",
                "numero_NF": nfe_record.numero_nfe or "",
                "serie": nfe_record.serie or "",
                "valor_NF": f"{nfe_record.valor_total_nfe or 0:.2f}".replace('.', ','),
                "dt_emissao_NF": nfe_record.data_emissao.strftime('%d/%m/%Y') if nfe_record.data_emissao else "",
                "Hdt_emissao_NF": nfe_record.data_emissao.strftime('%d/%m/%Y') if nfe_record.data_emissao else "",
                "dt_vencimento_NF": nfe_record.data_vencimento.strftime('%d/%m/%Y') if nfe_record.data_vencimento else "",
                "fornecedor": f"{nfe_record.nome_emitente} - {nfe_record.cnpj_emitente}",
                "cod_fornecedor": nfe_record.codigo_fornecedor or "N/A",
                "fm_pagamento": nfe_record.forma_pagamento or "N/A",
                "chk_boleto": "NAO",
                "justificativa": "NFe processada automaticamente pelo sistema.",
                "destinacao": nfe_record.natureza_operacao or "N/A",
                "column1_1___1": "02.007.014",
                "column1_2___1": nfe_record.descricao_produto or "",
                "projeto___1": "SEMPROJETO",
                "subprojeto___1": "SEMSUBPROJETO",
                "identificador": identificador,
                "documento_ged": attachment_id
            }
            
            start_process_payload = {
                "targetState": 59,
                "targetAssignee": "",
                "subProcessTargetState": 0,
                "comment": "Iniciado via API",
                "formFields": form_fields
            }
            
            logging.info("Iniciando processo de Lançamento de Nota Fiscal...")
            start_proc_resp = requests.post(
                f'{self.fluig_url}/process-management/api/v2/processes/Processo%20de%20Lançamento%20de%20Nota%20Fiscal/start',
                json=start_process_payload,
                auth=self.auth
            )
            start_proc_resp.raise_for_status()
            process_instance_id = start_proc_resp.json()["processInstanceId"]
            logging.info(f"Processo de serviço criado! ID: {process_instance_id}")
            return process_instance_id
            
        except Exception as e:
            logging.error(f"Erro ao iniciar processo de serviço: {str(e)}")
            raise
    
    def integrate_nfe_with_fluig(self, nfe_record_id):
        """
        Integra um registro NFE com o Fluig
        
        Args:
            nfe_record_id: ID do registro NFE
            
        Returns:
            dict: Resultado da integração
        """
        try:
            # Buscar o registro NFE
            nfe_record = NFERecord.query.get(nfe_record_id)
            if not nfe_record:
                raise ValueError(f"Registro NFE não encontrado: {nfe_record_id}")
            
            # Verificar se tem arquivo PDF original
            if not nfe_record.original_pdf_path or not os.path.exists(nfe_record.original_pdf_path):
                raise ValueError("Arquivo PDF original não encontrado")
            
            # 1. Upload do arquivo
            uploaded_file_name = self.upload_file_to_fluig(
                nfe_record.original_pdf_path,
                nfe_record.original_pdf_filename or f"nfe_{nfe_record.numero_nfe}.pdf"
            )
            
            # 2. Criar documento no GED
            attachment_id = self.create_document_in_ged(uploaded_file_name)
            
            # 3. Iniciar processo baseado no tipo de operação
            if nfe_record.tipo_operacao == "CT-e (Transporte)":
                process_id = self.start_transport_process(nfe_record, attachment_id)
                process_type = "Importação de Frete"
            else:
                process_id = self.start_service_process(nfe_record, attachment_id)
                process_type = "Lançamento de Nota Fiscal"
            
            # Atualizar registro com informações da integração
            nfe_record.fluig_process_id = process_id
            nfe_record.fluig_document_id = attachment_id
            nfe_record.fluig_integration_date = datetime.now()
            db.session.commit()
            
            return {
                "success": True,
                "process_id": process_id,
                "document_id": attachment_id,
                "process_type": process_type,
                "message": f"Integração realizada com sucesso! Processo {process_type} criado com ID: {process_id}"
            }
            
        except Exception as e:
            logging.error(f"Erro na integração com Fluig: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "message": f"Erro na integração: {str(e)}"
            }


def get_fluig_integration_for_user(user_id):
    """
    Obtém instância de integração Fluig para um usuário
    
    Args:
        user_id: ID do usuário
        
    Returns:
        FluigIntegration: Instância configurada ou None se não configurada
    """
    try:
        user_settings = UserSettings.get_or_create_for_user(user_id)
        
        if not user_settings.has_fluig_config:
            return None
            
        return FluigIntegration(user_settings)
        
    except Exception as e:
        logging.error(f"Erro ao obter integração Fluig para usuário {user_id}: {str(e)}")
        return None