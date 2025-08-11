#!/usr/bin/env python3
"""
Script de teste simplificado para integração do Fluig
Foca apenas no problema dos valores dos itens
"""

import logging
import json
from app import app, db
from models import NFERecord, NFEItem, UserSettings
from fluig_integration import FluigIntegration

def test_simple_integration():
    """Testa integração com foco nos valores"""
    
    with app.app_context():
        # Buscar NFE 11282 para teste
        nfe_record = NFERecord.query.filter(
            NFERecord.numero_nf == '11282'
        ).first()
        
        if not nfe_record:
            logging.error("NFE 11282 não encontrada!")
            return
        
        # Buscar configurações do usuário
        user_settings = UserSettings.query.filter_by(user_id=nfe_record.user_id).first()
        if not user_settings:
            logging.error("Configurações do usuário não encontradas!")
            return
        
        # Buscar primeiro item
        item = NFEItem.query.filter_by(nfe_record_id=nfe_record.id).first()
        if not item:
            logging.error("Item não encontrado!")
            return
        
        # Calcular valor do item
        valor_final = float(item.servico_valor) if item.servico_valor and item.servico_valor > 0 else 0
        if valor_final == 0:
            valor_final = float(nfe_record.valor_total_nf or 0)
        
        logging.info(f"🧪 TESTE DE INTEGRAÇÃO SIMPLIFICADO")
        logging.info(f"NFE: {nfe_record.numero_nf}")
        logging.info(f"Valor do item: R$ {valor_final:.2f}")
        
        # Campos mínimos para teste
        form_fields_test = {
            # Campos obrigatórios básicos
            "nome": "TESTE VALOR ITEM",
            "email": "teste@betunel.com.br",
            "numero_NF": nfe_record.numero_nf,
            "valor_NF": f"{nfe_record.valor_total_nf:.2f}".replace('.', ','),
            
            # TESTANDO DIFERENTES FORMATOS DE VALORES
            # Formato 1: Campos de tabela (atual)
            "column1_5___1": f"{valor_final:.2f}".replace('.', ','),  # Brasileiro
            "column1_5___1_us": f"{valor_final:.2f}",  # Americano
            
            # Formato 2: Campos diretos sem tabela
            "valorItem": f"{valor_final:.2f}".replace('.', ','),
            "valorItemUS": f"{valor_final:.2f}",
            "vlrItem": str(int(valor_final * 100)),  # Centavos
            
            # Formato 3: Campos simples
            "valor1": f"{valor_final:.2f}",
            "vlr1": f"{valor_final}",
            "preco1": f"{valor_final:.2f}".replace('.', ','),
            
            # Formato 4: Arrays ou listas
            "valoresItens": f"[{valor_final:.2f}]",
            "valoresItens_str": f"{valor_final:.2f}".replace('.', ','),
        }
        
        logging.info(f"📦 CAMPOS DE TESTE:")
        for campo, valor in form_fields_test.items():
            logging.info(f"  {campo}: '{valor}'")
        
        # Criar integração
        fluig = FluigIntegration(user_settings)
        
        # Payload de teste
        payload = {
            "attachments": [],
            "comment": "TESTE PARA VERIFICAR VALORES DOS ITENS",
            "formFields": form_fields_test
        }
        
        logging.info(f"🚀 ENVIANDO PAYLOAD DE TESTE...")
        logging.info(f"Total de campos: {len(form_fields_test)}")
        
        return payload

def simulate_api_call():
    """Simula chamada da API sem fazer requisição real"""
    
    payload = test_simple_integration()
    if payload:
        logging.info(f"✅ PAYLOAD CRIADO PARA TESTE")
        logging.info(f"JSON Preview:")
        print(json.dumps(payload, indent=2, ensure_ascii=False)[:500] + "...")
        
        logging.info(f"🔍 CAMPOS COM 'VALOR' NO NOME:")
        for campo in payload['formFields']:
            if 'valor' in campo.lower() or 'vlr' in campo.lower():
                logging.info(f"  {campo}: {payload['formFields'][campo]}")

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    simulate_api_call()