#!/usr/bin/env python3
"""
Script para descobrir o schema do formulário do Fluig
"""

import logging
import requests
from app import app, db
from models import UserSettings, User

def descobrir_schema_fluig():
    """Descobrir a estrutura do formulário do Fluig"""
    
    with app.app_context():
        # Pegar as configurações do usuário
        user_settings = UserSettings.query.first()
        if not user_settings:
            logging.error("Configurações não encontradas!")
            return
        
        logging.info(f"🔍 DESCOBRINDO SCHEMA DO FORMULÁRIO FLUIG")
        logging.info(f"URL: {user_settings.fluig_url}")
        
        # Construir autenticação OAuth1
        from requests_oauthlib import OAuth1
        auth = OAuth1(
            client_key=user_settings.fluig_consumer_key,
            client_secret=user_settings.fluig_consumer_secret,
            resource_owner_key=user_settings.fluig_token,
            resource_owner_secret=user_settings.fluig_token_secret,
            signature_method='HMAC-SHA1'
        )
        
        try:
            # Tentar obter detalhes do processo 
            process_url = f"{user_settings.fluig_url}/process-management/api/v2/processes/Processo%20de%20Lançamento%20de%20Nota%20Fiscal"
            
            logging.info(f"🔍 Consultando detalhes do processo...")
            response = requests.get(process_url, auth=auth, timeout=30)
            
            if response.status_code == 200:
                result = response.json()
                logging.info(f"✅ Processo encontrado!")
                logging.info(f"📋 Detalhes: {result}")
                
                # Tentar obter o formulário
                if 'formId' in result:
                    form_id = result['formId']
                    logging.info(f"🆔 Form ID: {form_id}")
                    
                    # Consultar campos do formulário
                    form_url = f"{user_settings.fluig_url}/form-management/api/v2/forms/{form_id}/fields"
                    logging.info(f"🔍 Consultando campos do formulário...")
                    
                    form_response = requests.get(form_url, auth=auth, timeout=30)
                    if form_response.status_code == 200:
                        fields = form_response.json()
                        logging.info(f"✅ Campos encontrados:")
                        for field in fields:
                            if 'name' in field and ('valor' in field['name'].lower() or 'vlr' in field['name'].lower() or 'column' in field['name'].lower()):
                                logging.info(f"   🎯 CAMPO RELEVANTE: {field}")
                    else:
                        logging.warning(f"⚠️ Não foi possível obter campos: {form_response.status_code}")
                        
            else:
                logging.error(f"❌ Erro ao consultar processo: {response.status_code} - {response.text}")
                
        except Exception as e:
            logging.error(f"❌ Erro: {e}")
            
        # Tentar uma abordagem alternativa - obter um processo existente
        logging.info(f"🔍 TENTATIVA ALTERNATIVA - Consultar processo existente...")
        try:
            # Usar um dos process IDs que sabemos que funcionam
            existing_process_url = f"{user_settings.fluig_url}/process-management/api/v2/processes/774005"
            
            response = requests.get(existing_process_url, auth=auth, timeout=30)
            if response.status_code == 200:
                process_data = response.json()
                logging.info(f"✅ Processo 774005 encontrado!")
                
                # Procurar por dados do formulário
                if 'formData' in process_data:
                    form_data = process_data['formData']
                    logging.info(f"📋 DADOS DO FORMULÁRIO EXISTENTE:")
                    for key, value in form_data.items():
                        if 'column' in key.lower() or 'valor' in key.lower():
                            logging.info(f"   🎯 {key}: {value}")
                            
            else:
                logging.warning(f"⚠️ Processo 774005 não encontrado: {response.status_code}")
                
        except Exception as e:
            logging.error(f"❌ Erro alternativa: {e}")

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    descobrir_schema_fluig()