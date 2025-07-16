"""
Fluig Integration Module
Handles integration with Fluig system for NFe processing
"""

import requests
from requests_oauthlib import OAuth1
import json
import logging
from datetime import datetime
from app import db
from models import UserSettings, NFERecord, Empresa, Filial
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
        
    def test_fluig_connection(self):
        """
        Testa a conexão com o Fluig
        
        Returns:
            dict: Resultado do teste
        """
        try:
            # Testar conexão básica
            response = requests.get(
                f'{self.fluig_url}/api/public/ecm/folder/getFolderContent/{self.ged_folder_id}',
                auth=self.auth,
                timeout=10
            )
            
            if response.status_code == 200:
                return {'success': True, 'message': 'Conexão com Fluig estabelecida com sucesso'}
            else:
                return {
                    'success': False, 
                    'message': f'Erro na conexão: Status {response.status_code} - {response.text[:200]}'
                }
                
        except requests.exceptions.ConnectionError:
            return {'success': False, 'message': 'Não foi possível conectar ao servidor Fluig'}
        except requests.exceptions.Timeout:
            return {'success': False, 'message': 'Timeout na conexão com o Fluig'}
        except Exception as e:
            return {'success': False, 'message': f'Erro inesperado: {str(e)}'}
        
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
    
    def create_workflow_launch(self, nfe_record, file_path):
        """
        Cria um novo lançamento no Fluig com o documento NFE usando processos existentes
        
        Args:
            nfe_record: Registro NFE com dados do documento
            file_path: Caminho do arquivo PDF
            
        Returns:
            dict: Resultado da criação do lançamento
        """
        try:
            # Primeiro, fazer upload do arquivo
            uploaded_file_name = self.upload_file_to_fluig(file_path, os.path.basename(file_path))
            
            # Criar documento no GED primeiro
            attachment_id = self.create_document_in_ged(uploaded_file_name, nfe_record)
            
            # Determinar o processo baseado no tipo de operação
            if nfe_record.tipo_operacao == "CT-e (Transporte)":
                # Usar processo de transporte existente
                process_id = self.start_transport_process(nfe_record, attachment_id)
                process_type = "Importação de Frete"
            else:
                # Usar processo de serviço existente
                process_id = self.start_service_process(nfe_record, attachment_id)
                process_type = "Lançamento de Nota Fiscal"
            
            logging.info(f"Processo {process_type} criado com sucesso. Process ID: {process_id}")
            return {
                'success': True,
                'process_id': process_id,
                'message': f'Processo {process_type} criado com sucesso',
                'process_type': process_type
            }
                
        except Exception as e:
            logging.error(f"Erro na criação do lançamento: {str(e)}")
            return {
                'success': False,
                'message': f'Erro inesperado: {str(e)}'
            }
    
    def find_accessible_folder(self):
        """
        Descobre automaticamente uma pasta com permissões de escrita
        
        Returns:
            int: ID da pasta acessível ou None se não encontrar
        """
        # Primeiro, tentar a pasta configurada
        if self.ged_folder_id:
            logging.info(f"Testando pasta configurada: {self.ged_folder_id}")
            test_result = self.test_folder_permission(self.ged_folder_id)
            if test_result['success']:
                logging.info(f"Pasta configurada {self.ged_folder_id} está acessível")
                return self.ged_folder_id
            else:
                logging.warning(f"Pasta configurada {self.ged_folder_id} não tem permissões: {test_result['message']}")
        
        # Se não tem pasta configurada ou ela não funciona, descobrir automaticamente
        logging.info("Descobrindo pasta funcional automaticamente...")
        
        # Listar todas as pastas disponíveis
        folders = self.list_available_folders()
        
        # Testar cada pasta até encontrar uma que funcione
        for folder in folders:
            logging.info(f"Testando pasta {folder['id']} ({folder['name']})")
            test_result = self.test_folder_permission(folder['id'])
            if test_result['success']:
                logging.info(f"Pasta funcional encontrada: {folder['id']} ({folder['name']})")
                return folder['id']
            else:
                logging.debug(f"Pasta {folder['id']} não tem permissões: {test_result['message']}")
        
        # Se não encontrou nenhuma pasta funcional
        logging.error("Nenhuma pasta com permissões de escrita foi encontrada")
        return None
    
    def list_available_folders(self):
        """
        Lista todas as pastas disponíveis para o usuário
        
        Returns:
            list: Lista de pastas com ID, nome e permissões
        """
        try:
            # Buscar pastas raiz primeiro
            response = requests.get(
                f"{self.fluig_url}/api/public/ecm/document/getDocuments",
                params={
                    'parentId': 0,
                    'limit': 100
                },
                auth=self.auth
            )
            response.raise_for_status()
            
            folders = []
            data = response.json()
            
            if 'content' in data:
                for item in data['content']:
                    if item.get('documentType') == 'folder':
                        folders.append({
                            'id': item['documentId'],
                            'name': item.get('description', f"Pasta {item['documentId']}"),
                            'parent': item.get('parentDocumentId', 0)
                        })
            
            # Buscar subpastas das pastas encontradas
            for folder in folders.copy():
                try:
                    sub_response = requests.get(
                        f"{self.fluig_url}/api/public/ecm/document/getDocuments",
                        params={
                            'parentId': folder['id'],
                            'limit': 50
                        },
                        auth=self.auth
                    )
                    if sub_response.status_code == 200:
                        sub_data = sub_response.json()
                        if 'content' in sub_data:
                            for sub_item in sub_data['content']:
                                if sub_item.get('documentType') == 'folder':
                                    folders.append({
                                        'id': sub_item['documentId'],
                                        'name': f"{folder['name']} / {sub_item.get('description', 'Pasta ' + str(sub_item['documentId']))}",
                                        'parent': sub_item.get('parentDocumentId', folder['id'])
                                    })
                except Exception:
                    continue
            
            return folders
            
        except Exception as e:
            logging.error(f"Erro ao listar pastas disponíveis: {str(e)}")
            return []
    
    def test_folder_permission(self, folder_id):
        """
        Testa se é possível criar documentos na pasta especificada
        
        Args:
            folder_id: ID da pasta para testar
            
        Returns:
            dict: Resultado do teste com sucesso/erro
        """
        try:
            # Fazer uma requisição de teste para verificar permissões
            test_data = {
                "description": "TESTE - Verificação de permissões",
                "parentId": folder_id,
                "documentTypeId": 7,
                "version": 1,
                "draft": True,  # Usar draft para não criar documento real
                "inheritSecurity": True
            }
            
            response = requests.post(
                f"{self.fluig_url}/api/public/ecm/document/createDocument",
                json=test_data,
                auth=self.auth
            )
            
            if response.status_code == 200:
                # Se criou com sucesso, deletar o documento de teste
                result = response.json()
                if 'content' in result:
                    doc_id = result['content'].get('documentId')
                    if doc_id:
                        try:
                            requests.delete(f"{self.fluig_url}/api/public/ecm/document/deleteDocument/{doc_id}", auth=self.auth)
                        except Exception:
                            pass
                
                return {
                    'success': True,
                    'message': 'Pasta acessível para criação de documentos'
                }
            else:
                error_msg = response.text
                try:
                    error_data = response.json()
                    if 'message' in error_data:
                        if isinstance(error_data['message'], dict):
                            error_msg = error_data['message'].get('message', error_msg)
                        else:
                            error_msg = str(error_data['message'])
                except:
                    pass
                
                return {
                    'success': False,
                    'message': f'Erro {response.status_code}: {error_msg}'
                }
                
        except Exception as e:
            return {
                'success': False,
                'message': f'Erro ao testar pasta: {str(e)}'
            }
    
    def create_document_in_ged(self, uploaded_file_name, nfe_record=None):
        """
        Cria um documento no GED do Fluig com informações específicas do NFE
        
        Args:
            uploaded_file_name: Nome do arquivo enviado
            nfe_record: Registro NFE com informações específicas do documento
            
        Returns:
            str: ID do documento criado
        """
        try:
            # Obter pasta a ser usada
            folder_id = self.find_accessible_folder()
            
            # Criar descrição específica do NFE
            if nfe_record:
                description = f"NFE {nfe_record.numero_nf} - {nfe_record.emitente_nome} - " \
                             f"Valor: R$ {nfe_record.valor_total_nf or 0:.2f} - " \
                             f"Data: {nfe_record.data_emissao.strftime('%d/%m/%Y') if nfe_record.data_emissao else 'N/A'} - " \
                             f"Tipo: {nfe_record.tipo_operacao or 'N/A'}"
            else:
                description = f"{uploaded_file_name} - Enviado via API"
            
            # Lista de estratégias para testar múltiplas pastas
            strategies = []
            
            # Adicionar pasta descoberta automaticamente se encontrada
            if folder_id:
                strategies.append({"parentId": int(folder_id), "description": description})
            
            # Adicionar pastas de fallback
            strategies.extend([
                {"parentId": 1, "description": description},  # Pasta raiz
                {"parentId": 2, "description": description},  # Pasta secundária
            ])
            
            # Tentar cada estratégia
            for strategy in strategies:
                try:
                    # Payload básico
                    create_doc_payload = {
                        "description": strategy["description"],
                        "parentId": strategy["parentId"],
                        "attachments": [{"fileName": uploaded_file_name}],
                        "documentTypeId": 7,
                        "version": 1,
                        "draft": False,
                        "inheritSecurity": True
                    }
                    
                    logging.info(f"Tentando criar documento na pasta {strategy['parentId']}")
                    
                    # Fazer a requisição
                    create_doc_resp = requests.post(
                        f'{self.fluig_url}/api/public/ecm/document/createDocument',
                        json=create_doc_payload,
                        auth=self.auth,
                        timeout=30
                    )
                    
                    if create_doc_resp.status_code == 200:
                        attachment_id = create_doc_resp.json()['content']['id']
                        logging.info(f"Documento criado com sucesso na pasta {strategy['parentId']} - ID: {attachment_id}")
                        return str(attachment_id)
                    else:
                        logging.info(f"Falha na pasta {strategy['parentId']}: {create_doc_resp.status_code} - {create_doc_resp.text}")
                        continue
                        
                except Exception as e:
                    logging.info(f"Erro na pasta {strategy['parentId']}: {str(e)}")
                    continue
            
            # Se chegou aqui, nenhuma estratégia funcionou
            raise Exception("Não foi possível criar documento em nenhuma pasta testada")
            
        except requests.exceptions.HTTPError as e:
            logging.error(f"HTTP Error ao criar documento no GED: {e}")
            logging.error(f"Status Code: {e.response.status_code}")
            logging.error(f"Response: {e.response.text}")
            raise
        except Exception as e:
            logging.error(f"Erro geral ao criar documento no GED: {str(e)}")
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
                cnpj=nfe_record.emitente_cnpj.replace('.', '').replace('/', '').replace('-', '')
            ).first()
            
            filial = None
            if empresa:
                filial = Filial.query.filter_by(
                    user_id=nfe_record.user_id,
                    coligada=empresa.numero,
                    cnpj_filial=nfe_record.emitente_cnpj.replace('.', '').replace('/', '').replace('-', '')
                ).first()
            
            # Montar identificador
            identificador = f"Empresa: {empresa.nome_fantasia if empresa else 'N/A'} " \
                          f"Fornecedor: {nfe_record.emitente_cnpj} - {nfe_record.emitente_nome} " \
                          f"Numero: {nfe_record.numero_nf} " \
                          f"Valor: {nfe_record.valor_total_nf or 0:.2f} " \
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
                "NOME_FORNECEDOR": nfe_record.emitente_nome or "",
                "numAtiv": "224",
                "numProc": "731485",
                "boletoAnexado": "",
                "prazo": "",
                "chave_acesso": nfe_record.chave_nfe or "",
                "tpDocXML": "CTE",
                "tpFreteXML": "2",
                "uniMedXML": "T",
                "aliqICMSXML": f"{nfe_record.valor_icms or 0:.2f}",
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
                "produtoXML": nfe_record.natureza_operacao or "",
                "chaveNFE": nfe_record.chave_nfe or "",
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
                "nomeItem___1": nfe_record.natureza_operacao or "",
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
                cnpj=nfe_record.emitente_cnpj.replace('.', '').replace('/', '').replace('-', '')
            ).first()
            
            filial = None
            if empresa:
                filial = Filial.query.filter_by(
                    user_id=nfe_record.user_id,
                    coligada=empresa.numero,
                    cnpj_filial=nfe_record.emitente_cnpj.replace('.', '').replace('/', '').replace('-', '')
                ).first()
            
            # Montar identificador
            identificador = f"Empresa: {empresa.nome_fantasia if empresa else 'N/A'} " \
                          f"Fornecedor: {nfe_record.emitente_nome} - {nfe_record.emitente_cnpj} " \
                          f"Numero: {nfe_record.numero_nf} " \
                          f"Valor: {nfe_record.valor_total_nf or 0:.2f} " \
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
                "cnpj": nfe_record.emitente_cnpj or "",
                "nm_filial": filial.nome_filial if filial else "N/A",
                "cod_filial": str(filial.filial) if filial else "1",
                "cnpj_filial": nfe_record.emitente_cnpj or "",
                "unid_negoc": "SUPPLY E CUSTOS",
                "cod_un": "0.10.02.01.001",
                "centro_custo": "1.0.3299 - SUPRIMENTOS",
                "cod_cc": "1.0.3299",
                "tp_doc": "Nota fiscal de serviço eletrônica",
                "numero_NF": nfe_record.numero_nf or "",
                "serie": nfe_record.serie or "",
                "valor_NF": f"{nfe_record.valor_total_nf or 0:.2f}".replace('.', ','),
                "dt_emissao_NF": nfe_record.data_emissao.strftime('%d/%m/%Y') if nfe_record.data_emissao else "",
                "Hdt_emissao_NF": nfe_record.data_emissao.strftime('%d/%m/%Y') if nfe_record.data_emissao else "",
                "dt_vencimento_NF": nfe_record.data_vencimento.strftime('%d/%m/%Y') if nfe_record.data_vencimento else "",
                "fornecedor": f"{nfe_record.emitente_nome} - {nfe_record.emitente_cnpj}",
                "cod_fornecedor": nfe_record.emitente_cnpj or "N/A",
                "fm_pagamento": nfe_record.forma_pagamento or "N/A",
                "chk_boleto": "NAO",
                "justificativa": "NFe processada automaticamente pelo sistema.",
                "destinacao": nfe_record.natureza_operacao or "N/A",
                "column1_1___1": "02.007.014",
                "column1_2___1": nfe_record.natureza_operacao or "",
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
    
    def start_transport_process_direct(self, nfe_record, uploaded_file_name):
        """
        Inicia processo de transporte diretamente sem criar documento no GED
        
        Args:
            nfe_record: Registro NFE com dados do documento
            uploaded_file_name: Nome do arquivo já enviado para o Fluig
            
        Returns:
            int: ID do processo criado
        """
        try:
            # Dados do cartão para processo de transporte
            card_data = {
                "NUMERO_NF": nfe_record.numero_nf or '',
                "EMITENTE": nfe_record.emitente_nome or '',
                "CNPJ_EMITENTE": nfe_record.emitente_cnpj or '',
                "VALOR_TOTAL": str(nfe_record.valor_total_nf or 0),
                "DATA_EMISSAO": nfe_record.data_emissao.strftime('%d/%m/%Y') if nfe_record.data_emissao else '',
                "CHAVE_NFE": nfe_record.chave_nfe or '',
                "TIPO_OPERACAO": nfe_record.tipo_operacao or 'CT-e (Transporte)',
                "ANEXO_NFE": uploaded_file_name,
                "OBSERVACOES": f"Documento processado automaticamente - NFE {nfe_record.numero_nf}"
            }
            
            # Criar processo de importação de frete
            process_data = {
                "processId": "ImportacaoFrete",
                "description": f"Importação de Frete - NFE {nfe_record.numero_nf}",
                "requester": "yasmim.silva@betunel.com.br",
                "priority": 1,
                "attachments": [uploaded_file_name],
                "cardData": card_data
            }
            
            response = requests.post(
                f"{self.fluig_url}/api/public/2.0/processes/start",
                json=process_data,
                auth=self.auth,
                timeout=60
            )
            
            if response.status_code == 200:
                result = response.json()
                process_id = result.get('processInstanceId')
                logging.info(f"Processo de transporte criado com sucesso. ID: {process_id}")
                return process_id
            else:
                logging.error(f"Erro ao criar processo de transporte: {response.status_code} - {response.text}")
                raise Exception(f"Erro ao criar processo: {response.status_code}")
                
        except Exception as e:
            logging.error(f"Erro ao iniciar processo de transporte direto: {str(e)}")
            raise
    
    def start_service_process_direct(self, nfe_record, uploaded_file_name):
        """
        Inicia processo de serviço diretamente sem criar documento no GED
        
        Args:
            nfe_record: Registro NFE com dados do documento
            uploaded_file_name: Nome do arquivo já enviado para o Fluig
            
        Returns:
            int: ID do processo criado
        """
        try:
            # Dados do cartão para processo de serviço
            card_data = {
                "NUMERO_NF": nfe_record.numero_nf or '',
                "EMITENTE": nfe_record.emitente_nome or '',
                "CNPJ_EMITENTE": nfe_record.emitente_cnpj or '',
                "VALOR_TOTAL": str(nfe_record.valor_total_nf or 0),
                "DATA_EMISSAO": nfe_record.data_emissao.strftime('%d/%m/%Y') if nfe_record.data_emissao else '',
                "CHAVE_NFE": nfe_record.chave_nfe or '',
                "TIPO_OPERACAO": nfe_record.tipo_operacao or 'Serviços e Produtos',
                "VALOR_SERVICOS": str(nfe_record.valor_servicos or 0),
                "VALOR_ISSQN": str(nfe_record.valor_issqn or 0),
                "ANEXO_NFE": uploaded_file_name,
                "OBSERVACOES": f"Documento processado automaticamente - NFE {nfe_record.numero_nf}"
            }
            
            # Criar processo de lançamento de nota fiscal
            process_data = {
                "processId": "LancamentoNF",
                "description": f"Lançamento de Nota Fiscal - NFE {nfe_record.numero_nf}",
                "requester": "yasmim.silva@betunel.com.br",
                "priority": 1,
                "attachments": [uploaded_file_name],
                "cardData": card_data
            }
            
            response = requests.post(
                f"{self.fluig_url}/api/public/2.0/processes/start",
                json=process_data,
                auth=self.auth,
                timeout=60
            )
            
            if response.status_code == 200:
                result = response.json()
                process_id = result.get('processInstanceId')
                logging.info(f"Processo de serviço criado com sucesso. ID: {process_id}")
                return process_id
            else:
                logging.error(f"Erro ao criar processo de serviço: {response.status_code} - {response.text}")
                raise Exception(f"Erro ao criar processo: {response.status_code}")
                
        except Exception as e:
            logging.error(f"Erro ao iniciar processo de serviço direto: {str(e)}")
            raise
    
    def integrate_nfe_with_fluig(self, nfe_record_id):
        """
        Integra um registro NFE com o Fluig usando processos existentes que já funcionavam
        
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
                nfe_record.original_pdf_filename or f"nfe_{nfe_record.numero_nf}.pdf"
            )
            
            # 2. Tentar criar documento no GED com fallback para processos diretos
            try:
                # Tentar criar no GED primeiro (método original que funcionava)
                attachment_id = self.create_document_in_ged(uploaded_file_name, nfe_record)
                
                # 3. Iniciar processo com attachment_id
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
                nfe_record.fluig_integration_status = 'INTEGRADO'
                db.session.commit()
                
                logging.info(f"NFE {nfe_record.numero_nf} integrado com sucesso. Process ID: {process_id}")
                return {
                    "success": True,
                    "process_id": process_id,
                    "document_id": attachment_id,
                    "process_type": process_type,
                    "message": f"Integração realizada com sucesso! Processo {process_type} criado com ID: {process_id}"
                }
                
            except Exception as ged_error:
                logging.warning(f"Erro ao criar documento no GED: {str(ged_error)}")
                logging.info("Tentando integração simples apenas com upload do arquivo...")
                
                # Fallback: Marcar como integrado apenas com upload
                nfe_record.fluig_integration_date = datetime.now()
                nfe_record.fluig_integration_status = 'ARQUIVO_ENVIADO'
                db.session.commit()
                
                return {
                    "success": True,
                    "process_type": "Upload de Arquivo",
                    "message": f"Arquivo enviado com sucesso para o Fluig. Arquivo: {uploaded_file_name}"
                }
            
        except Exception as e:
            logging.error(f"Erro na integração NFE com Fluig: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "message": f"Erro na integração: {str(e)}"
            }
    
    def integrate_nfe_with_fluig_legacy(self, nfe_record_id):
        """
        [LEGACY] Integra um registro NFE com o Fluig usando método antigo (pastas)
        Esta função será mantida como fallback se necessário
        
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
                nfe_record.original_pdf_filename or f"nfe_{nfe_record.numero_nf}.pdf"
            )
            
            # 2. Criar documento no GED com informações específicas do NFE
            attachment_id = self.create_document_in_ged(uploaded_file_name, nfe_record)
            
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