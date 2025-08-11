#!/usr/bin/env python3
"""
Script de debug para testar qual formato de valor o Fluig aceita
"""

import logging

def test_valor_formats():
    """Testa diferentes formatos de valores"""
    
    valor_original = 2965.20
    
    # Diferentes formatos
    formats = {
        "brasileiro_virgula": f"{valor_original:.2f}".replace('.', ','),
        "americano_ponto": f"{valor_original:.2f}",
        "inteiro_sem_decimal": str(int(valor_original)),
        "brasileiro_com_ponto_milhares": f"{valor_original:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.'),
        "string_simples": "2965.20",
        "string_brasileira": "2965,20"
    }
    
    logging.info("🧪 Testando formatos de valor:")
    for nome, valor in formats.items():
        logging.info(f"  {nome}: '{valor}'")
    
    return formats

def suggest_campo_names():
    """Sugere nomes de campos que o Fluig pode reconhecer"""
    
    campo_suggestions = [
        # Formatos básicos
        "column1_4___1",  # Padrão atual
        "column1_5___1",  # Padrão atual
        
        # Formatos sem underscores
        "valorItem1",
        "valorTotal1", 
        "qtd1",
        
        # Formatos com underscores simples
        "valor_item_1",
        "valor_total_1",
        "quantidade_1",
        
        # Formatos curtos
        "vlr1",
        "qtd1",
        "tot1",
        
        # Formatos longos
        "valorTotalDoItem1",
        "quantidadeDoItem1",
        "valorUnitarioDoItem1"
    ]
    
    logging.info("🏷️ Sugestões de nomes de campos:")
    for campo in campo_suggestions:
        logging.info(f"  {campo}")
    
    return campo_suggestions

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    test_valor_formats()
    suggest_campo_names()