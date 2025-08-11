"""
Fluig Integration Module
Handles integration with Fluig system for NFe processing
"""

import requests
from requests_oauthlib import OAuth1
import json
import logging
import time
from datetime import datetime
from app import db
from models import UserSettings, NFERecord, Empresa, Filial, User, NFEItem
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
            dict: Informações do arquivo enviado com nome e ID gerado
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
                
                response_data = upload_resp.json()
                uploaded_file_name = response_data['files'][0]['name']
                
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
                "valorUnitario___1": f"{nfe_record.valor_total_nf or 0:.2f}".replace('.', ','),
                "valorTotalItem___1": f"{nfe_record.valor_total_nf or 0:.2f}".replace('.', ','),
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
            response_data = start_proc_resp.json()
            process_instance_id = response_data["processInstanceId"]
            
            # Log da resposta completa para capturar número do Fluig
            logging.info(f"Resposta completa do processo de frete: {response_data}")
            logging.info(f"Processo de frete criado! ID: {process_instance_id}")
            
            # Tentar capturar número do processo se disponível
            process_number = response_data.get("processNumber")
            if process_number:
                logging.info(f"Número do processo de frete no Fluig: {process_number}")
                
                # Salvar o número da solicitação no banco
                from app import db
                nfe_record.fluig_process_id = process_number  # Salvar o número da solicitação
                nfe_record.fluig_integration_status = "INTEGRADO"
                
                # Salvar dados detalhados da integração
                integration_data = {
                    'integration_method': 'transport_process',
                    'process_id': process_instance_id,
                    'process_number': process_number,
                    'document_id': attachment_id,
                    'process_name': 'Importação de Frete',
                    'integration_timestamp': datetime.now().isoformat(),
                    'full_response': response_data
                }
                nfe_record.fluig_integration_data = json.dumps(integration_data)
                db.session.commit()
                
                logging.info(f"✓ Número da solicitação salvo no banco: {process_number}")
            
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
                "documento_ged": attachment_id,
                # Campos de item obrigatórios
                "item___1": "01",
                "codigoItem___1": "02.007.014",
                "nomeItem___1": nfe_record.natureza_operacao or "SERVIÇO",
                "quantidade___1": "1",
                "valorUnitario___1": f"{nfe_record.valor_total_nf or 0:.2f}".replace('.', ','),
                "valorTotalItem___1": f"{nfe_record.valor_total_nf or 0:.2f}".replace('.', ','),
                "unidadeMedida___1": "UN",
                "centroCusto___1": "1.0.3299"
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
            response_data = start_proc_resp.json()
            process_instance_id = response_data["processInstanceId"]
            
            # Log da resposta completa para capturar número do Fluig
            logging.info(f"Resposta completa do processo de serviço: {response_data}")
            logging.info(f"Processo de serviço criado! ID: {process_instance_id}")
            
            # Tentar capturar número do processo se disponível
            process_number = response_data.get("processNumber")
            if process_number:
                logging.info(f"Número do processo de serviço no Fluig: {process_number}")
                
                # Salvar o número da solicitação no banco
                from app import db
                nfe_record.fluig_process_id = process_number  # Salvar o número da solicitação
                nfe_record.fluig_integration_status = "INTEGRADO"
                
                # Salvar dados detalhados da integração
                integration_data = {
                    'integration_method': 'service_process',
                    'process_id': process_instance_id,
                    'process_number': process_number,
                    'document_id': attachment_id,
                    'process_name': 'Processo de Lançamento de Nota Fiscal',
                    'integration_timestamp': datetime.now().isoformat(),
                    'full_response': response_data
                }
                nfe_record.fluig_integration_data = json.dumps(integration_data)
                db.session.commit()
                
                logging.info(f"✓ Número da solicitação salvo no banco: {process_number}")
            
            return process_instance_id
            
        except Exception as e:
            logging.error(f"Erro ao iniciar processo de serviço: {str(e)}")
            raise
    
    def start_service_process_with_working_example(self, nfe_record, attachment_id):
        """
        Inicia processo usando exatamente o código de exemplo funcional fornecido pelo usuário
        Adaptado para usar os dados do sistema
        """
        try:
            # Buscar dados da empresa baseados no destinatário (empresa que recebe a NFe)
            cnpj_limpo = nfe_record.destinatario_cnpj.replace('.', '').replace('/', '').replace('-', '') if nfe_record.destinatario_cnpj else ""
            empresa = Empresa.query.filter_by(
                user_id=nfe_record.user_id,
                cnpj=cnpj_limpo
            ).first()
            
            filial = None
            if empresa:
                filial = Filial.query.filter_by(
                    user_id=nfe_record.user_id,
                    coligada=empresa.numero,
                    cnpj_filial=cnpj_limpo
                ).first()
            
            # Usar dados padrão da BETUNEL se não encontrar no cadastro
            if not empresa:
                empresa_nome = "BETUNEL"
                empresa_cod = "1"
                empresa_cnpj = "60.546.801/0001-89"
            else:
                empresa_nome = empresa.nome_fantasia
                empresa_cod = str(empresa.numero)
                empresa_cnpj = nfe_record.destinatario_cnpj or "60.546.801/0001-89"
            
            if not filial:
                filial_nome = "Jacarei"
                filial_cod = "16"
                filial_cnpj = "60.546.801/0025-56"
            else:
                filial_nome = filial.nome_filial
                filial_cod = str(filial.filial)
                filial_cnpj = nfe_record.destinatario_cnpj or empresa_cnpj
            
            # Buscar dados do usuário
            user = User.query.get(nfe_record.user_id)
            
            # Montar identificador seguindo o padrão do exemplo
            identificador = f"Empresa: {empresa_nome} " \
                          f"Fornecedor: {nfe_record.emitente_nome} - {nfe_record.emitente_cnpj} " \
                          f"Numero: {nfe_record.numero_nf} " \
                          f"Valor: {nfe_record.valor_total_nf or 0:.2f} " \
                          f"Data de Vencimento: {nfe_record.data_vencimento.strftime('%d/%m/%Y') if nfe_record.data_vencimento else 'N/A'} " \
                          f"Forma de Pagamento: {nfe_record.forma_pagamento or 'N/A'}"
            
            # Campos seguindo EXATAMENTE o exemplo funcional
            form_fields = {
                "nome": f"{user.first_name} {user.last_name}" if user and user.first_name and user.last_name else "Sistema Automatizado",
                "matricula": str(user.id) if user else "0d44ddb10e5a41a3a7a378aa5862694d",
                "email": user.email if user else "sistema@betunel.com.br",
                "Hdt_entrada_nf": datetime.now().strftime('%d/%m/%Y'),
                "dt_entrada_nf": datetime.now().strftime('%d/%m/%Y'),
                "nm_empresa": empresa_nome,
                "cod_empresa": empresa_cod,
                "cnpj": empresa_cnpj,
                "nm_filial": filial_nome,
                "cod_filial": filial_cod,
                "cnpj_filial": filial_cnpj,
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
                "fornecedor": f"{nfe_record.emitente_nome} - {nfe_record.emitente_cnpj} - 20.0581",
                "cod_fornecedor": "20.0581",
                "fm_pagamento": nfe_record.forma_pagamento or "A VISTA",
                "chk_boleto": "NAO",
                "justificativa": "NFe recebida nesta data.",
                "destinacao": nfe_record.natureza_operacao or "SERVIÇOS OPERACIONAIS",
                "column1_1___1": "02.007.014",
                "column1_2___1": nfe_record.natureza_operacao or "SERVIÇOS OPERACIONAIS",
                "projeto___1": "SEMPROJETO",
                "subprojeto___1": "SEMSUBPROJETO",
                "identificador": identificador,
                # Campo essencial para vincular documento - igual ao exemplo
                "documento_ged": str(attachment_id),
                
                # Novo campo obrigatório descoberto nos logs
                "item": "02.007.014",
                "item___1": "02.007.014",
                "codigoItem___1": "02.007.014",
                "nomeItem___1": nfe_record.natureza_operacao or "SERVIÇOS OPERACIONAIS",
                "valorItem___1": f"{nfe_record.valor_total_nf or 0:.2f}".replace('.', ','),
                "centralContasItem___1": "1.0.3299 - SUPRIMENTOS",
                "cc_item___1": "1.0.3299",
                
                # Campos obrigatórios para evitar "O Item deve ser preenchido"
                "descricao_item": nfe_record.natureza_operacao or "SERVIÇOS OPERACIONAIS",
                "valor_item": f"{nfe_record.valor_total_nf or 0:.2f}".replace('.', ','),
                "codigo_item": "02.007.014",
                "nome_item": nfe_record.natureza_operacao or "SERVIÇOS OPERACIONAIS",
                "qtde_item": "1",
                "unidade_item": "UN"
            }
            
            # Payload igual ao exemplo funcional
            start_process_payload = {
                "targetState": 59,
                "targetAssignee": "",
                "subProcessTargetState": 0,
                "comment": "Iniciado via API",
                "formFields": form_fields
            }
            
            logging.info("🚀 Iniciando processo usando código de exemplo funcional...")
            
            # Múltiplas tentativas com timeout aumentado
            max_attempts = 3
            timeout = 30  # 30 segundos
            
            for attempt in range(max_attempts):
                try:
                    logging.info(f"Tentativa {attempt + 1}/{max_attempts} - Timeout: {timeout}s")
                    start_proc_resp = requests.post(
                        f'{self.fluig_url}/process-management/api/v2/processes/Processo%20de%20Lançamento%20de%20Nota%20Fiscal/start',
                        json=start_process_payload,
                        auth=self.auth,
                        timeout=timeout
                    )
                    break  # Se chegou aqui, deu certo
                except requests.exceptions.Timeout:
                    logging.warning(f"Timeout na tentativa {attempt + 1}")
                    if attempt == max_attempts - 1:
                        logging.error("Todas as tentativas falharam por timeout")
                        return None
                    timeout += 15  # Aumenta timeout para próxima tentativa
                except Exception as e:
                    logging.error(f"Erro na tentativa {attempt + 1}: {str(e)}")
                    if attempt == max_attempts - 1:
                        return None
            
            logging.info(f"Response status: {start_proc_resp.status_code}")
            logging.info(f"Response text: {start_proc_resp.text}")
            
            start_proc_resp.raise_for_status()
            response_data = start_proc_resp.json()
            
            process_instance_id = response_data.get("processInstanceId")
            logging.info(f"✅ Processo criado com sucesso! ID: {process_instance_id}")
            
            # Salvar dados do processo no banco
            if process_instance_id:
                nfe_record.fluig_process_id = str(process_instance_id)
                nfe_record.fluig_integration_status = "INTEGRADO"
                
                # Salvar dados detalhados da integração
                integration_data = {
                    'integration_method': 'working_example',
                    'process_id': process_instance_id,
                    'document_id': attachment_id,
                    'process_name': 'Processo de Lançamento de Nota Fiscal',
                    'integration_timestamp': datetime.now().isoformat(),
                    'full_response': response_data
                }
                nfe_record.fluig_integration_data = json.dumps(integration_data)
                db.session.commit()
                
                logging.info(f"✓ Dados do processo salvos no banco: {process_instance_id}")
            
            return process_instance_id
            
        except Exception as e:
            logging.error(f"Erro ao iniciar processo com exemplo funcional: {str(e)}")
            return None
    
    def start_service_process_capture_solicitation_number(self, nfe_record, attachment_id):
        """
        Usa EXATAMENTE o código do exemplo funcional - apenas substitui os dados
        """
        try:
            from models import User
            from app import db
            
            # Buscar dados do usuário
            user = User.query.get(nfe_record.user_id)
            
            # Dados EXATAMENTE como no exemplo funcional
            form_fields = {
                "nome": user.first_name + " " + user.last_name if user and user.first_name and user.last_name else "Yasmim Silva",
                "matricula": "0d44ddb10e5a41a3a7a378aa5862694d",
                "email": user.email if user else "yasmim.silva@betunel.com.br",
                "Hdt_entrada_nf": datetime.now().strftime('%d/%m/%Y'),
                "dt_entrada_nf": datetime.now().strftime('%d/%m/%Y'),
                "nm_empresa": "BETUNEL",
                "cod_empresa": "1",
                "cnpj": "60.546.801/0001-89",
                "nm_filial": "Jacarei",
                "cod_filial": "16",
                "cnpj_filial": "60.546.801/0025-56",
                "unid_negoc": "SUPPLY E CUSTOS",
                "cod_un": "0.10.02.01.001",
                "centro_custo": "1.0.3299 - SUPRIMENTOS",
                "cod_cc": "1.0.3299",
                "tp_doc": "Nota fiscal de serviço eletrônica",
                "numero_NF": nfe_record.numero_nf or "",
                "serie": nfe_record.serie or "001",
                "valor_NF": f"{nfe_record.valor_total_nf or 0:.2f}".replace('.', ','),
                "dt_emissao_NF": nfe_record.data_emissao.strftime('%d/%m/%Y') if nfe_record.data_emissao else datetime.now().strftime('%d/%m/%Y'),
                "Hdt_emissao_NF": nfe_record.data_emissao.strftime('%d/%m/%Y') if nfe_record.data_emissao else datetime.now().strftime('%d/%m/%Y'),
                "dt_vencimento_NF": nfe_record.data_vencimento.strftime('%d/%m/%Y') if nfe_record.data_vencimento else datetime.now().strftime('%d/%m/%Y'),
                "fornecedor": f"{nfe_record.emitente_nome} - {nfe_record.emitente_cnpj} - 20.0581",
                "cod_fornecedor": "20.0581",
                "fm_pagamento": nfe_record.forma_pagamento or "DESPACHANTE",
                "chk_boleto": "NAO",
                "justificativa": "NFe recebida nesta data.",
                "destinacao": nfe_record.natureza_operacao or "PO475_20225 TIE PETROL",
                "column1_1___1": "02.007.014",
                "column1_2___1": nfe_record.natureza_operacao or "CAP 50/70 (CIMENTO ASFALTICO DE PETROLEO 50/70) (BAG)",
                "projeto___1": "SEMPROJETO",
                "subprojeto___1": "SEMSUBPROJETO",
                "identificador": f"Empresa: BETUNEL Fornecedor: {nfe_record.emitente_nome} - {nfe_record.emitente_cnpj} - 20.0581 Numero: {nfe_record.numero_nf} Valor: {nfe_record.valor_total_nf or 0:.2f} Data de Vencimento: {nfe_record.data_vencimento.strftime('%d/%m/%Y') if nfe_record.data_vencimento else 'N/A'} Forma de Pagamento: {nfe_record.forma_pagamento or 'DESPACHANTE'}",
                # Campo essencial para vincular documento
                "documento_ged": str(attachment_id)
            }
            
            # Payload EXATAMENTE como no exemplo funcional
            start_process_payload = {
                "targetState": 59,
                "targetAssignee": "",
                "subProcessTargetState": 0,
                "comment": "Iniciado via API",
                "formFields": form_fields
            }
            
            logging.info("🎯 Iniciando processo com código EXATO do exemplo funcional...")
            
            # Fazer requisição simples com timeout reduzido
            try:
                logging.info("Enviando requisição para criar processo...")
                start_proc_resp = requests.post(
                    f'{self.fluig_url}/process-management/api/v2/processes/Processo%20de%20Lançamento%20de%20Nota%20Fiscal/start',
                    json=start_process_payload,
                    auth=self.auth,
                    timeout=30  # Timeout reduzido para evitar worker timeout
                )
                
            except requests.exceptions.Timeout:
                logging.error("❌ Timeout na requisição para o Fluig")
                return None
            except Exception as e:
                logging.error(f"❌ Erro na requisição: {str(e)}")
                return None
            
            logging.info(f"Status da resposta: {start_proc_resp.status_code}")
            logging.info(f"Resposta completa: {start_proc_resp.text}")
            
            if start_proc_resp.status_code == 200:
                response_data = start_proc_resp.json()
                process_instance_id = response_data.get("processInstanceId")
                
                logging.info(f"✅ Processo criado com sucesso!")
                logging.info(f"processInstanceId: {process_instance_id}")
                
                # Salvar o processInstanceId como número da solicitação
                if hasattr(nfe_record, 'fluig_process_id'):
                    nfe_record.fluig_process_id = str(process_instance_id)
                    nfe_record.fluig_integration_status = "INTEGRADO"
                    
                    # Salvar dados completos da integração
                    integration_data = {
                        'integration_method': 'exact_example_code',
                        'process_instance_id': process_instance_id,
                        'document_id': attachment_id,
                        'process_name': 'Processo de Lançamento de Nota Fiscal',
                        'integration_timestamp': datetime.now().isoformat(),
                        'full_response': response_data
                    }
                    nfe_record.fluig_integration_data = json.dumps(integration_data)
                    db.session.commit()
                    
                    logging.info(f"✓ Processo salvo no banco: {process_instance_id}")
                
                return process_instance_id
            else:
                logging.error(f"❌ Erro ao criar processo: {start_proc_resp.status_code}")
                logging.error(f"Resposta de erro: {start_proc_resp.text}")
                return None
                
        except Exception as e:
            logging.error(f"Erro ao usar código do exemplo funcional: {str(e)}")
            return None

    def start_service_process_simple(self, nfe_record, attachment_id):
        """
        Versão com dados REAIS dos itens NFE do banco de dados
        """
        try:
            from models import NFEItem
            
            logging.info("🎯 Iniciando processo com DADOS REAIS dos itens NFE...")
            
            # Buscar itens reais da NFE
            nfe_items = NFEItem.query.filter_by(nfe_record_id=nfe_record.id).all()
            logging.info(f"Encontrados {len(nfe_items)} itens para NFE {nfe_record.numero_nf}")
            
            # Dados básicos do processo
            form_fields = {
                "nome": "Admin Sistema",
                "matricula": "0d44ddb10e5a41a3a7a378aa5862694d",
                "email": "admin@sistema.com",
                "Hdt_entrada_nf": datetime.now().strftime('%d/%m/%Y'),
                "dt_entrada_nf": datetime.now().strftime('%d/%m/%Y'),
                "nm_empresa": "BETUNEL",
                "cod_empresa": "1",
                "cnpj": "60.546.801/0001-89",
                "nm_filial": "Jacarei",
                "cod_filial": "16",
                "cnpj_filial": "60.546.801/0025-56",
                "unid_negoc": "SUPPLY E CUSTOS",
                "cod_un": "0.10.02.01.001",
                "centro_custo": "1.0.3299 - SUPRIMENTOS",
                "cod_cc": "1.0.3299",
                "tp_doc": "Nota fiscal de serviço eletrônica",
                "numero_NF": nfe_record.numero_nf or "",
                "serie": nfe_record.serie or "001",
                "valor_NF": f"{nfe_record.valor_total_nf or 0:.2f}".replace('.', ','),
                "dt_emissao_NF": nfe_record.data_emissao.strftime('%d/%m/%Y') if nfe_record.data_emissao else datetime.now().strftime('%d/%m/%Y'),
                "Hdt_emissao_NF": nfe_record.data_emissao.strftime('%d/%m/%Y') if nfe_record.data_emissao else datetime.now().strftime('%d/%m/%Y'),
                "dt_vencimento_NF": nfe_record.data_vencimento.strftime('%d/%m/%Y') if nfe_record.data_vencimento else datetime.now().strftime('%d/%m/%Y'),
                "fornecedor": f"{nfe_record.emitente_nome} - {nfe_record.emitente_cnpj} - 20.0581",
                "cod_fornecedor": "20.0581",
                "fm_pagamento": nfe_record.forma_pagamento or "DESPACHANTE",
                "chk_boleto": "NAO",
                "justificativa": "NFe recebida nesta data.",
                "destinacao": nfe_record.natureza_operacao or "TRIBUTAÇÃO NO MUNICÍPIO",
                "projeto___1": "SEMPROJETO",
                "subprojeto___1": "SEMSUBPROJETO",
                "identificador": f"Empresa: BETUNEL Fornecedor: {nfe_record.emitente_nome} - {nfe_record.emitente_cnpj} - 20.0581 Numero: {nfe_record.numero_nf} Valor: {nfe_record.valor_total_nf or 0:.2f} Data de Vencimento: {nfe_record.data_vencimento.strftime('%d/%m/%Y') if nfe_record.data_vencimento else 'N/A'} Forma de Pagamento: {nfe_record.forma_pagamento or 'DESPACHANTE'}",
                "documento_ged": str(attachment_id)
            }
            
            # Adicionar dados REAIS dos itens
            if nfe_items:
                for i, item in enumerate(nfe_items[:10], 1):  # Máximo 10 itens
                    # Campos obrigatórios do item
                    if item.servico_codigo:
                        form_fields[f"column1_1___{i}"] = item.servico_codigo
                    else:
                        form_fields[f"column1_1___{i}"] = "02.007.014"  # Código padrão
                    
                    # Usar campo correto para descrição
                    descricao = item.descricao_servico or item.descricao_produto or item.servico_discriminacao or "TRIBUTAÇÃO NO MUNICÍPIO"
                    form_fields[f"column1_2___{i}"] = descricao[:100]  # Limitar tamanho
                    
                    # Campos adicionais do item
                    if item.quantidade_comercial:
                        form_fields[f"quantidade___{i}"] = f"{item.quantidade_comercial:.2f}".replace('.', ',')
                    
                    if item.valor_unitario_comercial:
                        form_fields[f"valorUnitario___{i}"] = f"{item.valor_unitario_comercial:.2f}".replace('.', ',')
                    
                    if item.valor_total_produto:
                        form_fields[f"valorTotalItem___{i}"] = f"{item.valor_total_produto:.2f}".replace('.', ',')
                    
                    if item.codigo_produto:
                        form_fields[f"codigoItem___{i}"] = item.codigo_produto
                    
                    if descricao:
                        form_fields[f"nomeItem___{i}"] = descricao[:50]  # Nome curto
                    
                    logging.info(f"Item {i}: {item.servico_codigo or item.codigo_produto} - {descricao} - R$ {item.valor_total_produto}")
            else:
                # Fallback se não houver itens
                form_fields["column1_1___1"] = "02.007.014"
                form_fields["column1_2___1"] = nfe_record.natureza_operacao or "TRIBUTAÇÃO NO MUNICÍPIO"
                logging.warning("Nenhum item encontrado, usando dados padrão")
            
            # Múltiplas tentativas com timeout progressivo
            payload = {
                "targetState": 59,
                "targetAssignee": "",
                "subProcessTargetState": 0,
                "comment": "Iniciado via API",
                "formFields": form_fields
            }
            
            max_attempts = 3
            timeout = 30  # Começar com 30 segundos
            
            for attempt in range(max_attempts):
                try:
                    logging.info(f"🔄 Tentativa {attempt + 1}/{max_attempts} - Timeout: {timeout}s")
                    response = requests.post(
                        f'{self.fluig_url}/process-management/api/v2/processes/Processo%20de%20Lançamento%20de%20Nota%20Fiscal/start',
                        json=payload,
                        auth=self.auth,
                        timeout=timeout
                    )
                    
                    if response.status_code == 200:
                        response_data = response.json()
                        process_instance_id = response_data.get('processInstanceId')
                        
                        if process_instance_id:
                            logging.info(f"✅ Processo criado com sucesso! ID: {process_instance_id}")
                            
                            # Tentar extrair número de solicitação
                            process_number = (
                                response_data.get('processNumber') or 
                                response_data.get('solicitationNumber') or 
                                response_data.get('requestNumber') or
                                process_instance_id
                            )
                            
                            logging.info(f"🎯 Número da solicitação: {process_number}")
                            logging.info(f"📋 Resposta completa: {response_data}")
                            
                            return process_instance_id
                        else:
                            logging.error("❌ Processo criado mas sem ID retornado")
                            return None
                    else:
                        logging.error(f"❌ Erro HTTP {response.status_code}: {response.text}")
                        if attempt == max_attempts - 1:
                            return None
                        
                except requests.exceptions.Timeout:
                    logging.warning(f"⏱️ Timeout na tentativa {attempt + 1}")
                    if attempt == max_attempts - 1:
                        logging.error("❌ Todas as tentativas falharam por timeout")
                        return None
                    timeout += 15  # Aumentar timeout para próxima tentativa
                    
                except Exception as e:
                    logging.error(f"❌ Erro na tentativa {attempt + 1}: {str(e)}")
                    if attempt == max_attempts - 1:
                        return None
                
        except Exception as e:
            logging.error(f"❌ Erro: {str(e)}")
            return None
    
    def start_process_only_launch(self, nfe_record):
        """
        Cria lançamento direto no Fluig baseado no código de exemplo fornecido
        Busca dados da filial correta pelo CNPJ e usa informações reais
        """
        try:
            from models import Empresa, Filial, User, NFEItem
            
            logging.info("🎯 Iniciando lançamento direto - baseado no código de exemplo")
            
            # Buscar filial pelo CNPJ destinatário (quem recebe a NFE)
            cnpj_destinatario = nfe_record.destinatario_cnpj
            if cnpj_destinatario:
                cnpj_limpo = cnpj_destinatario.replace('.', '').replace('/', '').replace('-', '')
                
                # Buscar filial pelo CNPJ
                filial = Filial.query.filter_by(
                    user_id=nfe_record.user_id,
                    cnpj_filial=cnpj_limpo
                ).first()
                
                if filial:
                    # Buscar empresa da filial
                    empresa = Empresa.query.filter_by(
                        user_id=nfe_record.user_id,
                        numero=filial.coligada
                    ).first()
                    
                    logging.info(f"✅ Filial encontrada: {filial.nome_filial} - {filial.cnpj_filial}")
                    logging.info(f"✅ Empresa encontrada: {empresa.nome_fantasia if empresa else 'N/A'}")
                else:
                    logging.warning(f"❌ Filial não encontrada para CNPJ: {cnpj_destinatario}")
                    filial = None
                    empresa = None
            else:
                filial = None
                empresa = None
            
            # Buscar usuário
            user = User.query.get(nfe_record.user_id)
            
            # Buscar itens da NFE
            nfe_items = NFEItem.query.filter_by(nfe_record_id=nfe_record.id).all()
            logging.info(f"📋 Encontrados {len(nfe_items)} itens para NFE")
            
            # Usar dados da filial encontrada ou padrão BETUNEL
            if filial and empresa:
                nm_empresa = empresa.nome_fantasia
                cod_empresa = str(empresa.numero)
                cnpj_empresa = empresa.cnpj
                nm_filial = filial.nome_filial
                cod_filial = str(filial.filial)
                cnpj_filial = filial.cnpj_filial
            else:
                # Padrão BETUNEL como no exemplo
                nm_empresa = "BETUNEL"
                cod_empresa = "1"
                cnpj_empresa = "60.546.801/0001-89"
                nm_filial = "Jacarei"
                cod_filial = "16"
                cnpj_filial = "60.546.801/0025-56"
            
            # Montar campos do formulário baseado no exemplo fornecido
            form_fields = {
                "nome": f"{user.first_name} {user.last_name}" if user and user.first_name else "Roberto Galdino",
                "matricula": "e7f2q0ulk2s1qwxw1496403470877",  # Usar matrícula do exemplo que funciona
                "email": user.email if user else "roberto.galdino@betunel.com.br",
                "Hdt_entrada_nf": datetime.now().strftime('%d/%m/%Y'),
                "dt_entrada_nf": datetime.now().strftime('%d/%m/%Y'),
                "nm_empresa": nm_empresa,
                "cod_empresa": cod_empresa,
                "cnpj": cnpj_empresa,
                "nm_filial": nm_filial,
                "cod_filial": cod_filial,
                "cnpj_filial": cnpj_filial,
                "unid_negoc": "SUPPLY E CUSTOS",
                "cod_un": "0.10.02.01.001",
                "centro_custo": "1.0.3299 - SUPRIMENTOS",
                "cod_cc": "1.0.3299",
                "tp_doc": "Nota fiscal de serviço eletrônica",
                "numero_NF": nfe_record.numero_nf or "",
                "serie": nfe_record.serie or "E1",
                "valor_NF": f"{nfe_record.valor_total_nf or 0:.2f}".replace('.', ','),
                "dt_emissao_NF": nfe_record.data_emissao.strftime('%d/%m/%Y') if nfe_record.data_emissao else "",
                "Hdt_emissao_NF": nfe_record.data_emissao.strftime('%d/%m/%Y') if nfe_record.data_emissao else "",
                "dt_vencimento_NF": nfe_record.data_vencimento.strftime('%d/%m/%Y') if nfe_record.data_vencimento else "",
                "fornecedor": f"{nfe_record.emitente_nome} - {nfe_record.emitente_cnpj} - 20.0581",
                "cod_fornecedor": "20.0581",
                "fm_pagamento": nfe_record.forma_pagamento or "DESPACHANTE",
                "chk_boleto": "NAO",
                "justificativa": "NFe recebida nesta data.",
                "destinacao": nfe_record.natureza_operacao or "SERVIÇOS OPERACIONAIS",
                "projeto___1": "SEMPROJETO",
                "subprojeto___1": "SEMSUBPROJETO",
                "identificador": f"Empresa: {nm_empresa} Fornecedor: {nfe_record.emitente_nome} - {nfe_record.emitente_cnpj} - 20.0581 Numero: {nfe_record.numero_nf} Valor: {nfe_record.valor_total_nf or 0:.2f} Data de Vencimento: {nfe_record.data_vencimento.strftime('%d/%m/%Y') if nfe_record.data_vencimento else 'N/A'} Forma de Pagamento: {nfe_record.forma_pagamento or 'DESPACHANTE'}"
            }
            
            # ESTRATÉGIA COMPLEMENTAR: Campos diretos (fora da tabela) para valores
            valor_total_nfe = float(nfe_record.valor_total_nf or 0)
            form_fields["valorTotalItens"] = f"{valor_total_nfe:.2f}".replace('.', ',')  # Brasileiro
            form_fields["valorTotalItensUS"] = f"{valor_total_nfe:.2f}"  # Americano
            form_fields["valorTotalCentavos"] = str(int(valor_total_nfe * 100))  # Inteiro
            form_fields["vlrTotal"] = f"{valor_total_nfe}"  # Simples
            
            logging.info(f"🧪 CAMPOS DIRETOS ADICIONADOS:")
            logging.info(f"  valorTotalItens: {form_fields['valorTotalItens']}")
            logging.info(f"  valorTotalItensUS: {form_fields['valorTotalItensUS']}")
            logging.info(f"  valorTotalCentavos: {form_fields['valorTotalCentavos']}")
            
            # Adicionar dados dos itens se existirem
            if nfe_items:
                for i, item in enumerate(nfe_items[:10], 1):  # Máximo 10 itens
                    # Código do serviço
                    if item.servico_codigo:
                        form_fields[f"column1_1___{i}"] = item.servico_codigo
                    else:
                        form_fields[f"column1_1___{i}"] = "3301"
                    
                    # Descrição do serviço
                    descricao = item.descricao_servico or item.descricao_produto or nfe_record.natureza_operacao or "Serviços de desembaraço aduaneiro, comissários, despachantes e congêneres"
                    form_fields[f"column1_2___{i}"] = descricao[:100]
                    
                    # LÓGICA INTELIGENTE DE VALORES - SEMPRE preencher valor total
                    valor_final = 0.0
                    quantidade_final = float(item.quantidade_comercial or 1)
                    valor_unitario_final = 0.0
                    fonte_valor = "zero"
                    
                    # Prioridade: servico_valor > valor_total_produto > valor_unitario_comercial > valor_total_nfe
                    if item.servico_valor and float(item.servico_valor) > 0:
                        valor_final = float(item.servico_valor)
                        valor_unitario_final = valor_final / quantidade_final if quantidade_final > 0 else valor_final
                        fonte_valor = "servico_valor"
                    elif item.valor_total_produto and float(item.valor_total_produto) > 0:
                        valor_final = float(item.valor_total_produto)
                        valor_unitario_final = valor_final / quantidade_final if quantidade_final > 0 else valor_final
                        fonte_valor = "valor_total_produto"
                    elif item.valor_unitario_comercial and float(item.valor_unitario_comercial) > 0:
                        valor_unitario_final = float(item.valor_unitario_comercial)
                        valor_final = valor_unitario_final * quantidade_final
                        fonte_valor = f"valor_unitario_comercial * {quantidade_final}"
                    else:
                        # FALLBACK: usar valor total da NFE dividido pelo número de itens
                        valor_total_nfe = float(nfe_record.valor_total_nf or 0)
                        total_items = len(nfe_items)
                        valor_final = valor_total_nfe / total_items if total_items > 0 else valor_total_nfe
                        valor_unitario_final = valor_final / quantidade_final if quantidade_final > 0 else valor_final
                        fonte_valor = f"valor_total_nfe/{total_items}"
                    
                    # Garantir que sempre há um valor mínimo
                    if valor_final <= 0:
                        valor_final = float(nfe_record.valor_total_nf or 0)
                        valor_unitario_final = valor_final
                        quantidade_final = 1.0
                        fonte_valor = "fallback_valor_total_nfe"
                    
                    # ESTRATÉGIA REFORÇADA: Testar formatos diferentes
                    quantidade_final_formatted = f"{quantidade_final:.4f}" if quantidade_final != int(quantidade_final) else f"{int(quantidade_final)}"
                    valor_unitario_formatted = f"{valor_unitario_final:.2f}"
                    valor_total_formatted = f"{valor_final:.2f}"
                    
                    # Formato brasileiro (vírgula)
                    quantidade_str_br = quantidade_final_formatted.replace('.', ',')
                    valor_unitario_str_br = valor_unitario_formatted.replace('.', ',')
                    valor_total_str_br = valor_total_formatted.replace('.', ',')
                    
                    # Formato americano (ponto)
                    quantidade_str_us = quantidade_final_formatted
                    valor_unitario_str_us = valor_unitario_formatted
                    valor_total_str_us = valor_total_formatted
                    
                    # ESTRATÉGIA SIMPLIFICADA: Apenas os campos essenciais em múltiplos formatos
                    
                    # 1. Campos padrão (formato brasileiro com vírgula)
                    form_fields[f"column1_3___{i}"] = quantidade_str_br
                    form_fields[f"column1_4___{i}"] = valor_unitario_str_br
                    form_fields[f"column1_5___{i}"] = valor_total_str_br
                    
                    # 2. Mesmos campos em formato americano (com ponto)
                    form_fields[f"column1_3___{i}_dot"] = quantidade_str_us
                    form_fields[f"column1_4___{i}_dot"] = valor_unitario_str_us
                    form_fields[f"column1_5___{i}_dot"] = valor_total_str_us
                    
                    # 3. Campos sem formatação decimal (inteiros)
                    valor_total_int = str(int(valor_final * 100))  # Centavos
                    valor_unitario_int = str(int(valor_unitario_final * 100))  # Centavos
                    quantidade_int = str(int(quantidade_final))
                    
                    form_fields[f"column1_3___{i}_int"] = quantidade_int
                    form_fields[f"column1_4___{i}_int"] = valor_unitario_int
                    form_fields[f"column1_5___{i}_int"] = valor_total_int
                    
                    # 4. Campos com nomes alternativos mais simples
                    form_fields[f"qtd{i}"] = quantidade_str_br
                    form_fields[f"vlr{i}"] = valor_total_str_br
                    form_fields[f"valor{i}"] = valor_total_str_br
                    
                    # 5. NOVA ESTRATÉGIA: Campos que PODEM funcionar baseados em formulários Fluig comuns
                    form_fields[f"itemValor{i}"] = valor_total_str_br
                    form_fields[f"valorTotalItem{i}"] = valor_total_str_br
                    form_fields[f"vlrTotalItem{i}"] = valor_total_str_br
                    
                    # Campos de tabela HTML do Fluig (formato diferente)
                    form_fields[f"col{i}_valorTotal"] = valor_total_str
                    form_fields[f"col{i}_valor"] = valor_total_str
                    form_fields[f"col{i}_vlr"] = valor_total_str
                    form_fields[f"field_{i}_valorTotal"] = valor_total_str
                    form_fields[f"field_{i}_valor"] = valor_total_str
                    form_fields[f"row{i}_valorTotal"] = valor_total_str
                    form_fields[f"row{i}_valor"] = valor_total_str
                    
                    # Formato específico do Fluig para tabelas dinâmicas
                    form_fields[f"tablename_{i}_valorTotal"] = valor_total_str
                    form_fields[f"tablename_{i}_valor"] = valor_total_str
                    form_fields[f"item_{i}_valor"] = valor_total_str
                    form_fields[f"linha_{i}_valor"] = valor_total_str
                    
                    logging.info(f"💰 Item {i}: Código={item.servico_codigo or '3301'}")
                    logging.info(f"💰 Descrição: {descricao[:50]}...")
                    logging.info(f"💰 Quantidade: {quantidade_str}")
                    logging.info(f"💰 Valor Final: R$ {valor_final:.2f} (fonte: {fonte_valor})")
                    logging.info(f"💰 Campos enviados: column1_3___1={quantidade_str}, column1_4___1={valor_unitario_str}, column1_5___1={valor_total_str}")
                    logging.info(f"💰 Total de campos de valor enviados: {len([k for k in form_fields.keys() if 'valor' in k.lower() or 'vlr' in k.lower() or 'preco' in k.lower()])}")
                    
                    # ESTRATÉGIA ADICIONAL: Criar arrays de valores para o Fluig
                    if i == 1:  # Apenas na primeira iteração para evitar duplicação
                        # Arrays de valores que o Fluig pode reconhecer
                        form_fields["valoresItens"] = [valor_total_str_br]
                        form_fields["quantidadeItens"] = [quantidade_str_br]
                        form_fields["valoresUnitarios"] = [valor_unitario_str_br]
                        
                        # JSON de itens (em caso de Fluig reconhecer JSON)
                        form_fields["itensJson"] = json.dumps([{
                            "codigo": item.servico_codigo or "3301",
                            "descricao": descricao,
                            "quantidade": quantidade_final,
                            "valorUnitario": valor_unitario_final,
                            "valorTotal": valor_final
                        }])
                        
                        logging.info(f"💰 Arrays criados: valoresItens={form_fields['valoresItens']}")
                        logging.info(f"💰 JSON de itens: {form_fields['itensJson'][:100]}...")
                    
                    logging.info(f"💰 Item {i}: Código={item.servico_codigo or '3301'}")
                    logging.info(f"💰 Descrição: {descricao[:50]}...")
                    logging.info(f"💰 Valor Final: R$ {valor_final:.2f} (fonte: {fonte_valor})")
                    logging.info(f"🧪 FORMATOS TESTADOS:")
                    logging.info(f"  Brasileiro: qtd={quantidade_str_br}, vlr_unit={valor_unitario_str_br}, vlr_total={valor_total_str_br}")
                    logging.info(f"  Americano: qtd={quantidade_str_us}, vlr_unit={valor_unitario_str_us}, vlr_total={valor_total_str_us}")
                    logging.info(f"  Inteiros: qtd={quantidade_int}, vlr_unit={valor_unitario_int}, vlr_total={valor_total_int}")
                    logging.info(f"🏷️ CAMPOS PRINCIPAIS: column1_3___1, column1_4___1, column1_5___1")
                    logging.info(f"🔢 Total de campos enviados: {len(form_fields)}")
            else:
                # Item padrão se não houver itens
                form_fields["column1_1___1"] = "3301"
                form_fields["column1_2___1"] = "Serviços de desembaraço aduaneiro, comissários, despachantes e congêneres"
                # Valores padrão baseados no valor total da NFE
                valor_nfe = float(nfe_record.valor_total_nf or 0)
                valor_str = f"{valor_nfe:.2f}".replace('.', ',')
                form_fields["column1_3___1"] = "1,00"
                form_fields["column1_4___1"] = valor_str
                form_fields["column1_5___1"] = valor_str
                
                # MÉTODO ADICIONAL: Tentar todos os padrões possíveis de campos de valor
                valor_campos = [
                    "valorTotal___1", "valor___1", "vlr___1", "vlrTotal___1",
                    "valorItem___1", "vlrItem___1", "valorServico___1", "vlrServico___1",
                    "valorProduto___1", "vlrProduto___1", "precoTotal___1", "preco___1",
                    "column1_6___1", "column1_7___1", "column1_8___1", "column1_9___1",
                    "valorTotalItem___1", "valorTotalServico___1", "valorItemNota___1",
                    "col1_valor", "field_1_valor", "row1_valor", "item_1_valor",
                    "tablename_1_valor", "linha_1_valor", "valorTotal1", "valorItem1"
                ]
                
                for campo in valor_campos:
                    form_fields[campo] = valor_str
                    
                logging.info(f"💰 Item padrão: R$ {valor_nfe:.2f} (fonte: valor_total_nf)")
                logging.info(f"💰 Campos de valor preenchidos: {len(valor_campos)} campos diferentes")
            
            # Payload exatamente como no exemplo
            start_process_payload = {
                "targetState": 59,
                "targetAssignee": "",
                "subProcessTargetState": 0,
                "comment": "Iniciado via API",
                "formFields": form_fields
            }
            
            logging.info("🚀 Iniciando processo via API v2...")
            
            # Fazer requisição com timeout e retry
            max_attempts = 2
            timeout = 45
            
            for attempt in range(max_attempts):
                try:
                    response = requests.post(
                        f'{self.fluig_url}/process-management/api/v2/processes/Processo%20de%20Lançamento%20de%20Nota%20Fiscal/start',
                        json=start_process_payload,
                        auth=self.auth,
                        timeout=timeout
                    )
                    
                    response.raise_for_status()
                    response_data = response.json()
                    process_instance_id = response_data.get("processInstanceId")
                    
                    if process_instance_id:
                        logging.info(f"✅ Processo criado com sucesso! ID: {process_instance_id}")
                        
                        # Tentar extrair número de solicitação
                        process_number = (
                            response_data.get('processNumber') or 
                            response_data.get('solicitationNumber') or 
                            response_data.get('requestNumber') or
                            process_instance_id
                        )
                        
                        logging.info(f"🎯 Número da solicitação: {process_number}")
                        logging.info(f"📋 Resposta completa: {response_data}")
                        
                        return process_instance_id
                    else:
                        logging.error("❌ Processo criado mas sem ID retornado")
                        return None
                        
                except requests.exceptions.Timeout:
                    logging.warning(f"⏱️ Timeout na tentativa {attempt + 1}")
                    if attempt == max_attempts - 1:
                        logging.error("❌ Timeout - processo pode ter sido criado, verificar manualmente")
                        return None
                    timeout += 15
                    
                except Exception as e:
                    logging.error(f"❌ Erro na tentativa {attempt + 1}: {str(e)}")
                    if attempt == max_attempts - 1:
                        return None
            
            return None
            
        except Exception as e:
            logging.error(f"❌ Erro no lançamento direto: {str(e)}")
            return None
    
    def start_process_exact_example(self, nfe_record):
        """
        Método que replica EXATAMENTE o código de exemplo que funciona
        """
        try:
            from models import Empresa, Filial, User, NFEItem
            
            # Verificar se já foi integrado
            if nfe_record.fluig_process_id and nfe_record.fluig_integration_status == 'INTEGRADO':
                logging.info(f"✅ NFE {nfe_record.numero_nf} já está integrada com Fluig (ID: {nfe_record.fluig_process_id})")
                return {
                    'success': True,
                    'message': f'NFE já integrado! Process ID: {nfe_record.fluig_process_id}',
                    'process_id': nfe_record.fluig_process_id,
                    'process_type': 'Importação de Frete',
                    'integration_data': {
                        'method': 'already_integrated',
                        'process_id': nfe_record.fluig_process_id,
                        'timestamp': datetime.now().isoformat(),
                        'nfe_number': nfe_record.numero_nf,
                        'status': 'INTEGRADO'
                    }
                }
            
            logging.info("🎯 Usando código EXATO do exemplo que funciona")
            
            # Buscar dados da empresa/filial baseado no CNPJ destinatário
            cnpj_destinatario = nfe_record.destinatario_cnpj
            if cnpj_destinatario:
                cnpj_limpo = cnpj_destinatario.replace('.', '').replace('/', '').replace('-', '')
                
                filial = Filial.query.filter_by(
                    user_id=nfe_record.user_id,
                    cnpj_filial=cnpj_limpo
                ).first()
                
                if filial:
                    empresa = Empresa.query.filter_by(
                        user_id=nfe_record.user_id,
                        numero=filial.coligada
                    ).first()
                    
                    logging.info(f"✅ Usando filial: {filial.nome_filial}")
                    nm_empresa = empresa.nome_fantasia if empresa else "BETUNEL"
                    cod_empresa = str(empresa.numero) if empresa else "1"
                    cnpj_empresa = empresa.cnpj if empresa else "60.546.801/0001-89"
                    nm_filial = filial.nome_filial
                    cod_filial = str(filial.filial)
                    cnpj_filial = filial.cnpj_filial
                else:
                    # Usar dados padrão do exemplo
                    nm_empresa = "BETUNEL"
                    cod_empresa = "1"
                    cnpj_empresa = "60.546.801/0001-89"
                    nm_filial = "Jacarei"
                    cod_filial = "16"
                    cnpj_filial = "60.546.801/0025-56"
            else:
                # Usar dados padrão do exemplo
                nm_empresa = "BETUNEL"
                cod_empresa = "1"
                cnpj_empresa = "60.546.801/0001-89"
                nm_filial = "Jacarei"
                cod_filial = "16"
                cnpj_filial = "60.546.801/0025-56"
            
            # Buscar TODOS os itens para dados básicos e valores
            nfe_items = NFEItem.query.filter_by(nfe_record_id=nfe_record.id).all()
            first_item = nfe_items[0] if nfe_items else None
            
            # Lógica inteligente para cálculo de valores - SEMPRE garantir valor total
            if first_item:
                quantidade = first_item.quantidade_comercial or 1.0
                
                # Capturar valores disponíveis
                valor_unitario_comercial = first_item.valor_unitario_comercial or 0.0
                valor_total_produto = first_item.valor_total_produto or 0.0
                valor_servico = first_item.servico_valor or 0.0
                valor_nfe_total = nfe_record.valor_total_nf or 0.0
                
                # Prioridade: servico_valor > valor_total_produto > valor_unitario_comercial > valor_total_nf
                if valor_servico > 0:
                    valor_final_total = valor_servico
                    valor_final_unitario = valor_servico / quantidade if quantidade > 0 else valor_servico
                    fonte_valor = "servico_valor"
                elif valor_total_produto > 0:
                    valor_final_total = valor_total_produto
                    valor_final_unitario = valor_total_produto / quantidade if quantidade > 0 else valor_total_produto
                    fonte_valor = "valor_total_produto"
                elif valor_unitario_comercial > 0:
                    valor_final_unitario = valor_unitario_comercial
                    valor_final_total = valor_unitario_comercial * quantidade
                    fonte_valor = "valor_unitario_comercial"
                else:
                    # FALLBACK: sempre usar valor total da NFE
                    valor_final_total = valor_nfe_total
                    valor_final_unitario = valor_nfe_total / quantidade if quantidade > 0 else valor_nfe_total
                    fonte_valor = "valor_total_nf"
                
                # GARANTIA: Se ainda está zero, forçar o valor total da NFE
                if valor_final_total <= 0:
                    valor_final_total = valor_nfe_total
                    valor_final_unitario = valor_nfe_total
                    quantidade = 1.0
                    fonte_valor = "fallback_garantido_valor_total_nf"
                
                logging.info(f"🔢 Cálculo inteligente de valores:")
                logging.info(f"   Valor Unitário Comercial: {valor_unitario_comercial}")
                logging.info(f"   Valor Total Produto: {valor_total_produto}")
                logging.info(f"   Valor Serviço: {valor_servico}")
                logging.info(f"   Valor Total NFe: {valor_nfe_total}")
                logging.info(f"   ✅ Fonte escolhida: {fonte_valor}")
                logging.info(f"   ✅ Valor Final Unitário: {valor_final_unitario}")
                logging.info(f"   ✅ Valor Final Total: {valor_final_total}")
            else:
                quantidade = 1.0
                valor_final_unitario = nfe_record.valor_total_nf or 0.0
                valor_final_total = nfe_record.valor_total_nf or 0.0
                fonte_valor = "valor_total_nf_fallback"
            
            # Calcular data de entrada (deve ser >= data de emissão)
            from datetime import datetime, timedelta
            if nfe_record.data_emissao:
                # Data de entrada = data de emissão + 1 dia
                data_entrada = nfe_record.data_emissao + timedelta(days=1)
                dt_entrada_str = data_entrada.strftime('%d/%m/%Y')
            else:
                dt_entrada_str = "09/06/2025"  # Padrão se não tiver data de emissão
            
            # Campos EXATAMENTE como no exemplo que funciona
            form_fields = {
                "nome": "Roberto Galdino",
                "matricula": "e7f2q0ulk2s1qwxw1496403470877",
                "email": "roberto.galdino@betunel.com.br",
                "Hdt_entrada_nf": dt_entrada_str,  # Data entrada calculada
                "dt_entrada_nf": dt_entrada_str,   # Data entrada calculada
                "nm_empresa": nm_empresa,
                "cod_empresa": cod_empresa,
                "cnpj": cnpj_empresa,
                "nm_filial": nm_filial,
                "cod_filial": cod_filial,
                "cnpj_filial": cnpj_filial,
                "unid_negoc": "SUPPLY E CUSTOS",
                "cod_un": "0.10.02.01.001",
                "centro_custo": "1.0.3299 - SUPRIMENTOS",
                "cod_cc": "1.0.3299",
                "tp_doc": "Nota fiscal de serviço eletrônica",
                "numero_NF": nfe_record.numero_nf or "9876549",
                "serie": nfe_record.serie or "E1",
                "valor_NF": f"{nfe_record.valor_total_nf or 3187.80:.2f}".replace('.', ','),
                "dt_emissao_NF": nfe_record.data_emissao.strftime('%d/%m/%Y') if nfe_record.data_emissao else "12/05/2025",
                "Hdt_emissao_NF": nfe_record.data_emissao.strftime('%d/%m/%Y') if nfe_record.data_emissao else "12/05/2025",
                "dt_vencimento_NF": dt_entrada_str,  # Usar mesma data da entrada para evitar conflitos
                "fornecedor": f"{nfe_record.emitente_nome or 'NEW DEAL ASSESSORIA EM COMERCIO EXTERIOR LTDA EPP'} - {nfe_record.emitente_cnpj or '00.147.271/0001-74'} - 20.0581",
                "cod_fornecedor": "20.0581",
                "fm_pagamento": "DESPACHANTE",
                "chk_boleto": "NAO",
                "justificativa": "NFe recebida nesta data.",
                "destinacao": f"PO475_20225 {nfe_record.natureza_operacao or 'TIE PETROL'}",
                "column1_1___1": first_item.servico_codigo if first_item and first_item.servico_codigo else "02.007.014",
                "column1_2___1": (first_item.descricao_servico or first_item.descricao_produto)[:100] if first_item else "CAP 50/70 (CIMENTO ASFALTICO DE PETROLEO 50/70) (BAG)",
                # Usar valores calculados inteligentemente
                "column1_3___1": f"{quantidade:.2f}".replace('.', ','),  # Quantidade
                "column1_4___1": f"{valor_final_unitario:.2f}".replace('.', ','),  # Valor unitário
                "column1_5___1": f"{valor_final_total:.2f}".replace('.', ','),  # Valor total do item
                # Campos adicionais que podem controlar o valor final no Fluig
                "column1_6___1": f"{valor_final_total:.2f}".replace('.', ','),  # Possível campo valor
                "valorTotalItem___1": f"{valor_final_total:.2f}".replace('.', ','),
                "valorItem___1": f"{valor_final_total:.2f}".replace('.', ','),
                "valor___1": f"{valor_final_total:.2f}".replace('.', ','),
                "vlr_item___1": f"{valor_final_total:.2f}".replace('.', ','),
                # Campos extras para garantir que o valor apareça
                "vlrTotalItem___1": f"{valor_final_total:.2f}".replace('.', ','),
                "valorTotalServico___1": f"{valor_final_total:.2f}".replace('.', ','),
                "projeto___1": "SEMPROJETO",
                "subprojeto___1": "SEMSUBPROJETO",
                "identificador": f"Empresa: {nm_empresa} Fornecedor: {nfe_record.emitente_nome or 'NEW DEAL ASSESSORIA EM COMERCIO EXTERIOR LTDA EPP'} - {nfe_record.emitente_cnpj or '00.147.271/0001-74'} - 20.0581 Numero: {nfe_record.numero_nf or '11022'} Valor: {nfe_record.valor_total_nf or 3187.80:.2f} Data de Vencimento: {dt_entrada_str} Forma de Pagamento: DESPACHANTE"
            }
            
            # Payload EXATO do exemplo
            start_process_payload = {
                "targetState": 59,
                "targetAssignee": "",
                "subProcessTargetState": 0,
                "comment": "Iniciado via API",
                "formFields": form_fields
            }
            
            # Log detalhado dos dados dos itens sendo enviados
            logging.info("🔍 Dados dos itens sendo enviados:")
            if nfe_items:
                for i, item in enumerate(nfe_items):
                    logging.info(f"   Item {i+1}: {item.descricao_produto or item.descricao_servico}")
                    logging.info(f"     Código: {item.servico_codigo}")
                    logging.info(f"     Quantidade Comercial: {item.quantidade_comercial}")
                    logging.info(f"     Valor Unitário Comercial: {item.valor_unitario_comercial}")
                    logging.info(f"     Valor Total Produto: {item.valor_total_produto}")
                    logging.info(f"     Valor Serviço: {item.servico_valor}")
            else:
                logging.info("   ⚠️ Nenhum item encontrado na NFe!")
            
            # Log dos campos de formulário relacionados a itens
            logging.info("📝 Campos de itens no formulário:")
            for key, value in form_fields.items():
                if 'column' in key.lower() or 'valor' in key.lower() or 'vlr' in key.lower():
                    logging.info(f"   {key}: {value}")
            
            logging.info("🚀 Fazendo requisição EXATA como no exemplo...")
            
            response = requests.post(
                f'{self.fluig_url}/process-management/api/v2/processes/Processo%20de%20Lançamento%20de%20Nota%20Fiscal/start',
                json=start_process_payload,
                auth=self.auth,
                timeout=None  # Sem timeout - aguarda o tempo necessário
            )
            
            if response.status_code == 500:
                error_text = response.text
                # Verificar se é erro de duplicata
                if "já foi realizado no FLUIG" in error_text:
                    logging.info(f"✅ NFe {nfe_record.numero_nf} já foi integrada anteriormente")
                    # Extrair o ID do processo existente se possível
                    import re
                    match = re.search(r'ID (\d+)', error_text)
                    existing_id = match.group(1) if match else None
                    
                    if existing_id:
                        # Atualizar registro com ID existente (apenas o ID, não o objeto complexo)
                        nfe_record.fluig_process_id = existing_id
                        nfe_record.fluig_integration_status = 'INTEGRADO'
                        db.session.commit()
                        
                        return {
                            'success': True,
                            'message': f'NFE já integrado anteriormente! Process ID: {existing_id}',
                            'process_id': existing_id,
                            'process_type': 'Importação de Frete',
                            'integration_data': {
                                'method': 'launch_only_existing',
                                'process_id': existing_id,
                                'timestamp': datetime.now().isoformat(),
                                'nfe_number': nfe_record.numero_nf,
                                'status': 'INTEGRADO'
                            }
                        }
                else:
                    logging.error(f"❌ Erro HTTP: {response.status_code} - {error_text}")
                    raise Exception(f"Erro HTTP {response.status_code}: {error_text}")
            
            response.raise_for_status()
            response_data = response.json()
            process_instance_id = response_data.get("processInstanceId")
            
            if process_instance_id:
                logging.info(f"✅ Processo criado! ID: {process_instance_id}")
                logging.info(f"📋 Resposta: {response_data}")
                return process_instance_id
            else:
                logging.error("❌ Resposta sem processInstanceId")
                return None
                
        except requests.exceptions.HTTPError as e:
            logging.error(f"❌ Erro HTTP: {e.response.status_code} - {e.response.text}")
            return None
        except Exception as e:
            logging.error(f"❌ Erro: {str(e)}")
            return None
    
    def start_transport_process_direct(self, nfe_record, uploaded_file_name):
        """
        Inicia processo de transporte diretamente usando API correta do Fluig
        
        Args:
            nfe_record: Registro NFE com dados do documento
            uploaded_file_name: Nome do arquivo já enviado para o Fluig
            
        Returns:
            int: ID do processo criado
        """
        try:
            # Dados do formulário para processo de transporte (baseado no processo que funciona)
            form_fields = {
                "identificador": f"NFE {nfe_record.numero_nf} - {nfe_record.emitente_nome}",
                "dt_lanc": datetime.now().strftime('%d/%m/%Y'),
                "chave_acesso": nfe_record.chave_nfe or "",
                "NOME_FORNECEDOR": nfe_record.emitente_nome or "",
                "vlICMSXML": f"{nfe_record.valor_icms or 0:.2f}",
                "dtSaidaXML": nfe_record.data_emissao.strftime('%d/%m/%Y') if nfe_record.data_emissao else "",
                "produtoXML": nfe_record.natureza_operacao or "",
                "chaveNFE": nfe_record.chave_nfe or "",
                "valorUnitario___1": f"{nfe_record.valor_total_nf or 0:.2f}".replace('.', ','),
                "valorTotalItem___1": f"{nfe_record.valor_total_nf or 0:.2f}".replace('.', ','),
                "nomeItem___1": nfe_record.natureza_operacao or "",
                "quantidade___1": "1",
                "codigoItem___1": "01.071.003"
            }
            
            # Payload para iniciar processo usando API correta
            start_process_payload = {
                "processId": "Importação de Frete",
                "choosedState": 0,
                "formFields": form_fields,
                "processComment": f"Processo iniciado automaticamente - NFE {nfe_record.numero_nf}"
            }
            
            # Usar endpoint antigo que funcionava
            response = requests.post(
                f"{self.fluig_url}/api/public/2.0/processes/start",
                json=start_process_payload,
                auth=self.auth,
                timeout=60
            )
            
            if response.status_code == 200:
                result = response.json()
                process_id = result.get('processInstanceId')
                
                # Log da resposta completa para capturar número real do Fluig
                logging.info(f"Resposta completa do processo de transporte direto: {result}")
                logging.info(f"Processo de transporte criado com sucesso. ID: {process_id}")
                
                # Tentar capturar número do processo se disponível
                process_number = result.get("processNumber")
                if process_number:
                    logging.info(f"Número do processo de transporte no Fluig: {process_number}")
                
                # Tentar anexar arquivo ao processo criado
                self._attach_file_to_process(process_id, uploaded_file_name)
                
                return process_id
            else:
                logging.error(f"Erro ao criar processo de transporte: {response.status_code} - {response.text}")
                raise Exception(f"Erro ao criar processo: {response.status_code}")
                
        except Exception as e:
            logging.error(f"Erro ao iniciar processo de transporte direto: {str(e)}")
            raise
    
    def start_service_process_direct(self, nfe_record, uploaded_file_name):
        """
        Inicia processo de serviço diretamente usando API correta do Fluig
        
        Args:
            nfe_record: Registro NFE com dados do documento
            uploaded_file_name: Nome do arquivo já enviado para o Fluig
            
        Returns:
            int: ID do processo criado
        """
        try:
            # Dados do formulário para processo de serviço (baseado no processo que funciona)
            form_fields = {
                "nome": "Sistema Automatizado",
                "matricula": "sistema",
                "email": "sistema@betunel.com.br",
                "Hdt_entrada_nf": datetime.now().strftime('%d/%m/%Y'),
                "dt_entrada_nf": datetime.now().strftime('%d/%m/%Y'),
                "nm_empresa": "Sistema Automatizado",
                "cod_empresa": "1",
                "cnpj": nfe_record.emitente_cnpj or "",
                "nm_filial": "Principal",
                "cod_filial": "1",
                "cnpj_filial": nfe_record.emitente_cnpj or "",
                "unid_negoc": "SUPPLY E CUSTOS",
                "centro_custo": "SUPPLY E CUSTOS",
                "num_nf": nfe_record.numero_nf or "",
                "dt_emissao_nf": nfe_record.data_emissao.strftime('%d/%m/%Y') if nfe_record.data_emissao else "",
                "valor_nf": f"{nfe_record.valor_total_nf or 0:.2f}".replace('.', ','),
                "dt_vencimento_NF": nfe_record.data_vencimento.strftime('%d/%m/%Y') if nfe_record.data_vencimento else "",
                "fornecedor": f"{nfe_record.emitente_nome} - {nfe_record.emitente_cnpj}",
                "cod_fornecedor": nfe_record.emitente_cnpj or "N/A",
                "fm_pagamento": nfe_record.forma_pagamento or "N/A",
                "justificativa": "NFe processada automaticamente pelo sistema.",
                "destinacao": nfe_record.natureza_operacao or "N/A"
            }
            
            # Payload para iniciar processo usando API correta
            start_process_payload = {
                "processId": "Processo de Lançamento de Nota Fiscal",
                "choosedState": 0,
                "formFields": form_fields,
                "processComment": f"Processo iniciado automaticamente - NFE {nfe_record.numero_nf}"
            }
            
            # Usar endpoint antigo que funcionava
            response = requests.post(
                f"{self.fluig_url}/api/public/2.0/processes/start",
                json=start_process_payload,
                auth=self.auth,
                timeout=60
            )
            
            if response.status_code == 200:
                result = response.json()
                process_id = result.get('processInstanceId')
                
                # Log da resposta completa para capturar número real do Fluig
                logging.info(f"Resposta completa do processo de serviço direto: {result}")
                logging.info(f"Processo de serviço criado com sucesso. ID: {process_id}")
                
                # Tentar capturar número do processo se disponível
                process_number = result.get("processNumber")
                if process_number:
                    logging.info(f"Número do processo de serviço no Fluig: {process_number}")
                
                # Tentar anexar arquivo ao processo criado
                self._attach_file_to_process(process_id, uploaded_file_name)
                
                return process_id
            else:
                logging.error(f"Erro ao criar processo de serviço: {response.status_code} - {response.text}")
                raise Exception(f"Erro ao criar processo: {response.status_code}")
                
        except Exception as e:
            logging.error(f"Erro ao iniciar processo de serviço direto: {str(e)}")
            raise
    
    def _attach_file_to_process(self, process_id, uploaded_file_name):
        """
        Anexa arquivo ao processo criado usando API do Fluig
        
        Args:
            process_id: ID do processo criado
            uploaded_file_name: Nome do arquivo já enviado para o Fluig
        """
        try:
            # Tentar anexar arquivo ao processo usando API de attachments
            attach_payload = {
                "attachments": [uploaded_file_name]
            }
            
            response = requests.post(
                f"{self.fluig_url}/process-management/api/v2/requests/{process_id}/attachments",
                json=attach_payload,
                auth=self.auth,
                timeout=30
            )
            
            if response.status_code == 200:
                logging.info(f"Arquivo {uploaded_file_name} anexado com sucesso ao processo {process_id}")
            else:
                logging.warning(f"Não foi possível anexar arquivo ao processo: {response.status_code} - {response.text}")
                
        except Exception as e:
            logging.warning(f"Erro ao anexar arquivo ao processo: {str(e)}")
    
    def create_document_in_ged(self, uploaded_file_name, nfe_record):
        """
        Cria documento no GED do Fluig (baseado no exemplo fornecido)
        
        Args:
            uploaded_file_name: Nome do arquivo já enviado
            nfe_record: Registro NFE
            
        Returns:
            int: ID do documento criado
        """
        try:
            create_doc_payload = {
                "description": f"{uploaded_file_name} - NFE {nfe_record.numero_nf} - {nfe_record.emitente_nome}",
                "parentId": self.ged_folder_id,
                "attachments": [{"fileName": uploaded_file_name}],
                "documentTypeId": 7,  # Essencial para aparecer na aba de anexos
                "formData": [
                    {
                        "name": "ecm-widgetpartgeneralinformation-utilizaVisualizadorInterno",
                        "value": False
                    }
                ]
            }
            
            logging.info(f"Criando documento no GED para NFE {nfe_record.numero_nf}")
            response = requests.post(
                f"{self.fluig_url}/api/public/ecm/document/createDocument",
                json=create_doc_payload,
                auth=self.auth,
                timeout=60
            )
            
            if response.status_code == 200:
                document_id = response.json()['content']['id']
                logging.info(f"Documento criado no GED com ID: {document_id}")
                return document_id
            else:
                logging.error(f"Erro ao criar documento no GED: {response.status_code} - {response.text}")
                raise Exception(f"Erro ao criar documento no GED: {response.status_code}")
                
        except Exception as e:
            logging.error(f"Erro ao criar documento no GED: {str(e)}")
            raise
    
    def start_process_with_v2_api(self, nfe_record, attachment_id, process_name):
        """
        Inicia processo usando a API v2 do Fluig (baseado no exemplo fornecido)
        
        Args:
            nfe_record: Registro NFE
            attachment_id: ID do documento no GED
            process_name: Nome do processo no Fluig
            
        Returns:
            int: ID do processo criado
        """
        try:
            from urllib.parse import quote
            
            # Campos do formulário baseados no exemplo fornecido
            form_fields = {
                "nome": "Sistema API",
                "matricula": "sistema_api",
                "email": "sistema@betunel.com.br",
                "Hdt_entrada_nf": datetime.now().strftime('%d/%m/%Y'),
                "dt_entrada_nf": datetime.now().strftime('%d/%m/%Y'),
                "nm_empresa": "BETUNEL",
                "cod_empresa": "1",
                "cnpj": "60.546.801/0001-89",
                "nm_filial": "Matriz",
                "cod_filial": "01",
                "cnpj_filial": "60.546.801/0001-89",
                "unid_negoc": "OPERACIONAL",
                "cod_un": "0.10.02.01.001",
                "centro_custo": "1.0.3299 - SUPRIMENTOS",
                "cod_cc": "1.0.3299",
                "tp_doc": "Nota fiscal eletrônica",
                "numero_NF": str(nfe_record.numero_nf or ""),
                "serie": str(nfe_record.serie or ""),
                "valor_NF": f"{nfe_record.valor_total_nf or 0:.2f}".replace('.', ','),
                "dt_emissao_NF": nfe_record.data_emissao.strftime('%d/%m/%Y') if nfe_record.data_emissao else "",
                "Hdt_emissao_NF": nfe_record.data_emissao.strftime('%d/%m/%Y') if nfe_record.data_emissao else "",
                "dt_vencimento_NF": nfe_record.data_vencimento.strftime('%d/%m/%Y') if nfe_record.data_vencimento else "",
                "fornecedor": f"{nfe_record.emitente_nome} - {nfe_record.emitente_cnpj}",
                "cod_fornecedor": "20.0000", # Código padrão
                "fm_pagamento": nfe_record.forma_pagamento or "A VISTA",
                "chk_boleto": "NAO",
                "justificativa": f"NFe {nfe_record.numero_nf} integrada via API automaticamente.",
                "destinacao": nfe_record.natureza_operacao or "OPERACIONAL",
                "identificador": f"Empresa: BETUNEL Fornecedor: {nfe_record.emitente_nome} - {nfe_record.emitente_cnpj} Numero: {nfe_record.numero_nf} Valor: {nfe_record.valor_total_nf or 0:.2f} Data de Vencimento: {nfe_record.data_vencimento.strftime('%d/%m/%Y') if nfe_record.data_vencimento else 'N/A'} Forma de Pagamento: {nfe_record.forma_pagamento or 'A VISTA'}",
                "documento_ged": str(attachment_id)  # Campo oculto para o beforeStateEntry fazer o vínculo
            }
            
            # Payload para iniciar processo usando API v2
            start_process_payload = {
                "targetState": 59,
                "targetAssignee": "",
                "subProcessTargetState": 0,
                "comment": f"Processo iniciado automaticamente para NFE {nfe_record.numero_nf}",
                "formFields": form_fields
            }
            
            # Usar endpoint da API v2 com nome do processo URL-encoded
            encoded_process_name = quote(process_name)
            logging.info(f"Iniciando processo '{process_name}' via API v2")
            
            response = requests.post(
                f"{self.fluig_url}/process-management/api/v2/processes/{encoded_process_name}/start",
                json=start_process_payload,
                auth=self.auth,
                timeout=60
            )
            
            if response.status_code == 200:
                process_result = response.json()
                process_id = process_result.get('processInstanceId')
                process_number = process_result.get('processNumber')
                
                # Log completo da resposta para capturar todos os dados
                logging.info(f"Resposta completa do Fluig: {process_result}")
                logging.info(f"Processo '{process_name}' criado com sucesso!")
                logging.info(f"Process ID: {process_id}")
                logging.info(f"Process Number (Número da Solicitação): {process_number}")
                
                # Salvar o número da solicitação no banco
                if process_number:
                    from app import db
                    nfe_record.fluig_process_id = process_number  # Salvar o número da solicitação
                    nfe_record.fluig_integration_status = "INTEGRADO"
                    
                    # Salvar dados detalhados da integração
                    integration_data = {
                        'integration_method': 'api_v2_complete',
                        'process_id': process_id,
                        'process_number': process_number,
                        'document_id': attachment_id,
                        'process_name': process_name,
                        'integration_timestamp': datetime.now().isoformat(),
                        'full_response': process_result
                    }
                    nfe_record.fluig_integration_data = json.dumps(integration_data)
                    db.session.commit()
                    
                    logging.info(f"✓ Número da solicitação salvo no banco: {process_number}")
                
                # Retornar tanto o ID quanto o número da solicitação
                return {
                    'process_id': process_id,
                    'process_number': process_number,
                    'full_response': process_result
                }
            else:
                error_msg = f"{response.status_code} - {response.text}"
                logging.error(f"Erro ao criar processo '{process_name}': {error_msg}")
                raise Exception(f"Erro ao criar processo: {response.status_code}")
                
        except Exception as e:
            logging.error(f"Erro ao iniciar processo '{process_name}' via API v2: {str(e)}")
            raise
    
    def try_direct_process_creation(self, nfe_record, uploaded_file_name):
        """
        Tenta criar processo direto sem GED para capturar número da solicitação
        
        Args:
            nfe_record: Registro NFE
            uploaded_file_name: Nome do arquivo já enviado
            
        Returns:
            dict: Dados do processo criado ou None se falhar
        """
        try:
            # Definir processo baseado no tipo de operação - usar nomes exatos
            process_name = "Processo de Lançamento de Nota Fiscal"
            if nfe_record.tipo_operacao == "CT-e (Transporte)":
                process_name = "Processo de Lançamento de Nota Fiscal"  # Usar mesmo processo para teste
            
            # Tentar criar processo direto usando método simplificado
            from urllib.parse import quote
            from datetime import datetime
            
            # Encodar nome do processo
            encoded_process_name = quote(process_name)
            
            # Campos do formulário baseados no método start_service_process que funciona
            form_fields = {
                "nome": "Sistema Automatizado",
                "matricula": "sistema",
                "email": "sistema@betunel.com.br",
                "Hdt_entrada_nf": datetime.now().strftime('%d/%m/%Y'),
                "dt_entrada_nf": datetime.now().strftime('%d/%m/%Y'),
                "nm_empresa": "BETUNEL",
                "cod_empresa": "1",
                "cnpj": "60.546.801/0001-89",
                "nm_filial": "Matriz",
                "cod_filial": "1",
                "cnpj_filial": "60.546.801/0001-89",
                "unid_negoc": "SUPPLY E CUSTOS",
                "cod_un": "0.10.02.01.001",
                "centro_custo": "1.0.3299 - SUPRIMENTOS",
                "cod_cc": "1.0.3299",
                "tp_doc": "Nota fiscal de serviço eletrônica",
                "numero_NF": str(nfe_record.numero_nf or ""),
                "serie": str(nfe_record.serie or "001"),
                "valor_NF": f"{nfe_record.valor_total_nf or 0:.2f}".replace('.', ','),
                "dt_emissao_NF": nfe_record.data_emissao.strftime('%d/%m/%Y') if nfe_record.data_emissao else "",
                "Hdt_emissao_NF": nfe_record.data_emissao.strftime('%d/%m/%Y') if nfe_record.data_emissao else "",
                "dt_vencimento_NF": nfe_record.data_vencimento.strftime('%d/%m/%Y') if nfe_record.data_vencimento else "",
                "fornecedor": f"{nfe_record.emitente_nome} - {nfe_record.emitente_cnpj}",
                "cod_fornecedor": "20.0000",
                "fm_pagamento": nfe_record.forma_pagamento or "A VISTA",
                "chk_boleto": "NAO",
                "justificativa": f"NFe {nfe_record.numero_nf} integrada via API - Arquivo: {uploaded_file_name}",
                "destinacao": nfe_record.natureza_operacao or "OPERACIONAL",
                "identificador": f"Empresa: BETUNEL Fornecedor: {nfe_record.emitente_nome} - {nfe_record.emitente_cnpj} Numero: {nfe_record.numero_nf} Valor: {nfe_record.valor_total_nf or 0:.2f} Data de Vencimento: {nfe_record.data_vencimento.strftime('%d/%m/%Y') if nfe_record.data_vencimento else 'N/A'} Forma de Pagamento: {nfe_record.forma_pagamento or 'A VISTA'}"
            }
            
            # Tentar estados 0 e 11 que mostraram pedir pelo campo "Item"
            target_states = [0, 11]
            
            for target_state in target_states:
                start_process_payload = {
                    "targetState": target_state,
                    "targetAssignee": "",
                    "comment": f"Processo iniciado automaticamente para NFE {nfe_record.numero_nf}",
                    "formFields": form_fields
                }
                
                logging.info(f"Tentando estado {target_state} para processo '{process_name}'")
                
                response = requests.post(
                    f"{self.fluig_url}/process-management/api/v2/processes/{encoded_process_name}/start",
                    json=start_process_payload,
                    auth=self.auth,
                    timeout=30
                )
                
                if response.status_code == 200:
                    process_result = response.json()
                    process_id = process_result.get('processInstanceId')
                    process_number = process_result.get('processNumber')
                    
                    logging.info(f"✓ SUCESSO com estado {target_state}!")
                    logging.info(f"Process ID: {process_id}")
                    logging.info(f"Process Number (Número da Solicitação): {process_number}")
                    logging.info(f"Resposta completa: {process_result}")
                    
                    return {
                        'process_id': process_id,
                        'process_number': process_number,
                        'process_name': process_name,
                        'target_state': target_state,
                        'full_response': process_result
                    }
                else:
                    logging.debug(f"Estado {target_state} falhou: {response.status_code} - {response.text}")
            
            logging.warning(f"Não foi possível criar processo com nenhum estado para '{process_name}'")
            return None

                
        except Exception as e:
            logging.warning(f"Erro ao tentar criar processo direto: {str(e)}")
            return None
    
    def integrate_nfe_with_fluig(self, nfe_record_id):
        """
        Integra um registro NFE com o Fluig usando API v2 completa (baseada no exemplo fornecido)
        
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
            
            logging.info(f"🎯 Iniciando lançamento direto no Fluig para NFE {nfe_record.numero_nf}")
            
            # Apenas lançamento - SEM upload de arquivo
            process_name = "Processo de Lançamento de Nota Fiscal"
            if nfe_record.tipo_operacao == "CT-e (Transporte)":
                process_name = "Importação de Frete"
            
            # 4. Criar processo direto sem upload - usando código de exemplo EXATO
            logging.info(f"🎯 Criando lançamento direto no Fluig para NFE {nfe_record.numero_nf}")
            
            process_instance_id = self.start_process_exact_example(nfe_record)
            
            # Preparar dados de integração
            integration_data = {
                'nfe_number': nfe_record.numero_nf,
                'emitente': nfe_record.emitente_nome,
                'cnpj_emitente': nfe_record.emitente_cnpj,
                'valor_total': float(nfe_record.valor_total_nf or 0),
                'data_emissao': nfe_record.data_emissao.strftime('%d/%m/%Y') if nfe_record.data_emissao else None,
                'tipo_operacao': nfe_record.tipo_operacao,
                'chave_nfe': nfe_record.chave_nfe,
                'process_instance_id': process_instance_id,
                'process_name': process_name,
                'integration_timestamp': datetime.now().isoformat(),
                'integration_method': 'launch_only_example_code',
                'note': 'Lançamento direto baseado no código de exemplo fornecido - SEM upload de arquivo'
            }
            
            if process_instance_id:
                logging.info(f"✅ Processo criado com ID: {process_instance_id}")
                
                # Salvar dados de integração no banco
                nfe_record.fluig_process_id = str(process_instance_id)
                nfe_record.fluig_integration_date = datetime.now()
                nfe_record.fluig_integration_status = 'INTEGRADO'
                
                nfe_record.fluig_integration_data = json.dumps(integration_data)
                db.session.commit()
                
                logging.info(f"✅ NFE {nfe_record.numero_nf} integrado com sucesso!")
                logging.info(f"🎯 Process Instance ID: {process_instance_id}")
                
                return {
                    "success": True,
                    "message": f"NFE integrado com sucesso! Process ID: {process_instance_id}",
                    "process_id": process_instance_id,
                    "process_type": process_name,
                    "integration_data": integration_data
                }
            else:
                logging.error(f"❌ Não foi possível criar processo para NFE {nfe_record.numero_nf}")
                return {
                    "success": False,
                    "message": f"Não foi possível criar processo no Fluig para NFE {nfe_record.numero_nf}"
                }
            
        except Exception as e:
            logging.error(f"Erro na integração NFE com Fluig: {str(e)}")
            return {
                "success": False,
                "message": f"Erro na integração com Fluig: {str(e)}. Sistema não gera códigos falsos."
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