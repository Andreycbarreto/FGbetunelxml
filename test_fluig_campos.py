#!/usr/bin/env python3
"""
Script para testar especificamente os campos de valores no Fluig
"""

import logging
import json
from app import app, db
from models import NFERecord, NFEItem
from fluig_integration import FluigIntegration
from models import UserSettings

def test_campo_formats():
    """Testa diferentes formatos de nomes de campos para valores"""
    
    with app.app_context():
        # Buscar um NFE record para teste
        nfe_record = NFERecord.query.filter(
            NFERecord.numero_nf == '11282'
        ).first()
        
        if not nfe_record:
            logging.error("NFE 11282 não encontrada!")
            return
            
        # Buscar itens
        items = NFEItem.query.filter_by(nfe_record_id=nfe_record.id).all()
        if not items:
            logging.error("Nenhum item encontrado!")
            return
            
        item = items[0]  # Primeiro item
        
        # Calcular valor (mesmo código da integração)
        valor_final = 0
        fonte_valor = "default"
        
        if hasattr(item, 'servico_valor') and item.servico_valor and item.servico_valor > 0:
            valor_final = float(item.servico_valor)
            fonte_valor = "servico_valor"
        elif hasattr(item, 'valor_total_produto') and item.valor_total_produto and item.valor_total_produto > 0:
            valor_final = float(item.valor_total_produto)
            fonte_valor = "valor_total_produto"
        elif hasattr(item, 'valor_unitario_comercial') and item.valor_unitario_comercial and hasattr(item, 'quantidade_comercial') and item.quantidade_comercial:
            if item.valor_unitario_comercial > 0 and item.quantidade_comercial > 0:
                valor_final = float(item.valor_unitario_comercial) * float(item.quantidade_comercial)
                fonte_valor = "calc_unit_x_qty"
        
        if valor_final == 0:
            # Fallback para valor total da NFE dividido por items
            valor_final = float(nfe_record.valor_total_nf or 0) / len(items) if len(items) > 0 else float(nfe_record.valor_total_nf or 0)
            fonte_valor = "nfe_total_divided"
        
        logging.info(f"🔍 ANÁLISE DO ITEM:")
        logging.info(f"  NFE: {nfe_record.numero_nf}")
        logging.info(f"  Item: {item.servico_discriminacao or 'Sem descrição'}")
        logging.info(f"  Valor final: R$ {valor_final:.2f}")
        logging.info(f"  Fonte: {fonte_valor}")
        
        # Diferentes formatos de valores
        formatos_valor = {
            "brasileiro_virgula": f"{valor_final:.2f}".replace('.', ','),
            "americano_ponto": f"{valor_final:.2f}",
            "inteiro_centavos": str(int(valor_final * 100)),
            "string_simples": str(valor_final),
            "sem_formatacao": f"{valor_final}",
        }
        
        logging.info(f"💰 FORMATOS DE VALOR TESTADOS:")
        for nome, valor in formatos_valor.items():
            logging.info(f"  {nome}: '{valor}'")
        
        # Diferentes nomes de campos
        nomes_campos = [
            "column1_5___1",  # Padrão atual
            "valorItem1",
            "valorTotal1", 
            "vlr1",
            "valor1",
            "valorTotalItem1",
            "item1Valor",
            "valor_item_1",
            "vlrItem1",
            "precoItem1"
        ]
        
        logging.info(f"🏷️ NOMES DE CAMPOS TESTADOS:")
        for nome in nomes_campos:
            logging.info(f"  {nome}")
        
        # Sugestão de payload mínimo para teste
        payload_minimo = {
            "column1_5___1": f"{valor_final:.2f}".replace('.', ','),
            "valorItem1": f"{valor_final:.2f}",
            "vlr1": str(int(valor_final * 100)),
            "valor1": f"{valor_final}"
        }
        
        logging.info(f"📦 PAYLOAD MÍNIMO SUGERIDO:")
        logging.info(json.dumps(payload_minimo, indent=2))

def analyze_successful_integration():
    """Analisa uma integração que foi bem sucedida"""
    
    with app.app_context():
        # Buscar integração bem sucedida
        successful_nfe = NFERecord.query.filter(
            NFERecord.fluig_integration_status == 'INTEGRADO',
            NFERecord.fluig_process_id.isnot(None)
        ).first()
        
        if not successful_nfe:
            logging.info("❌ Nenhuma integração bem sucedida encontrada")
            return
            
        logging.info(f"✅ INTEGRAÇÃO BEM SUCEDIDA ENCONTRADA:")
        logging.info(f"  NFE: {successful_nfe.numero_nf}")
        logging.info(f"  Process ID: {successful_nfe.fluig_process_id}")
        logging.info(f"  Status: {successful_nfe.fluig_integration_status}")
        
        if successful_nfe.fluig_integration_data:
            try:
                integration_data = json.loads(successful_nfe.fluig_integration_data)
                logging.info(f"  Dados da integração:")
                logging.info(json.dumps(integration_data, indent=2))
            except:
                logging.info(f"  Dados raw: {successful_nfe.fluig_integration_data}")

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    test_campo_formats()
    analyze_successful_integration()