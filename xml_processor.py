import os
import logging
from lxml import etree
from datetime import datetime
from decimal import Decimal
import re

logger = logging.getLogger(__name__)

class NFEXMLProcessor:
    """Processes NFe XML files and extracts structured data."""
    
    def __init__(self):
        # NFe namespace mapping
        self.namespaces = {
            'nfe': 'http://www.portalfiscal.inf.br/nfe',
            'ds': 'http://www.w3.org/2000/09/xmldsig#'
        }
    
    def process_xml_file(self, file_path):
        """
        Process an NFe XML file and extract all relevant data.
        
        Args:
            file_path (str): Path to the XML file
            
        Returns:
            dict: Extracted NFe data
        """
        try:
            # Parse XML file
            tree = etree.parse(file_path)
            root = tree.getroot()
            
            # Extract data from different sections
            data = {}
            
            # Basic document identification
            data.update(self._extract_identification(root))
            
            # Emitente (Issuer) data
            data.update(self._extract_emitente(root))
            
            # Destinatário (Recipient) data
            data.update(self._extract_destinatario(root))
            
            # Totals
            data.update(self._extract_totals(root))
            
            # Transport information
            data.update(self._extract_transport(root))
            
            # Payment information
            data.update(self._extract_payment(root))
            
            # Protocol information
            data.update(self._extract_protocol(root))
            
            # Items/Products
            data['items'] = self._extract_items(root)
            
            # Store raw XML for reference
            data['raw_xml'] = etree.tostring(root, encoding='unicode', pretty_print=True)
            
            return data
            
        except Exception as e:
            logger.error(f"Error processing XML file {file_path}: {str(e)}")
            raise
    
    def _extract_identification(self, root):
        """Extract identification data (IDE section)."""
        data = {}
        
        try:
            ide = root.find('.//nfe:ide', self.namespaces)
            if ide is not None:
                data['numero_nf'] = self._get_text(ide, 'nfe:nNF')
                data['serie'] = self._get_text(ide, 'nfe:serie')
                data['modelo'] = self._get_text(ide, 'nfe:mod')
                data['natureza_operacao'] = self._get_text(ide, 'nfe:natOp')
                data['tipo_operacao'] = '1' if self._get_text(ide, 'nfe:tpNF') == '1' else '0'
                
                # Extract dates
                dh_emi = self._get_text(ide, 'nfe:dhEmi')
                if dh_emi:
                    data['data_emissao'] = self._parse_datetime(dh_emi)
                
                dh_sai_ent = self._get_text(ide, 'nfe:dhSaiEnt')
                if dh_sai_ent:
                    data['data_saida_entrada'] = self._parse_datetime(dh_sai_ent)
                
                # Environment (Produção/Homologação)
                tp_amb = self._get_text(ide, 'nfe:tpAmb')
                data['ambiente'] = 'Produção' if tp_amb == '1' else 'Homologação'
        
        except Exception as e:
            logger.warning(f"Error extracting identification data: {str(e)}")
        
        # Extract NFe key from infNFe id attribute
        try:
            inf_nfe = root.find('.//nfe:infNFe', self.namespaces)
            if inf_nfe is not None:
                nfe_id = inf_nfe.get('Id', '')
                if nfe_id.startswith('NFe'):
                    data['chave_nfe'] = nfe_id[3:]  # Remove 'NFe' prefix
        except Exception as e:
            logger.warning(f"Error extracting NFe key: {str(e)}")
        
        return data
    
    def _extract_emitente(self, root):
        """Extract issuer data (EMIT section)."""
        data = {}
        
        try:
            emit = root.find('.//nfe:emit', self.namespaces)
            if emit is not None:
                data['emitente_cnpj'] = self._get_text(emit, 'nfe:CNPJ')
                data['emitente_nome'] = self._get_text(emit, 'nfe:xNome')
                data['emitente_fantasia'] = self._get_text(emit, 'nfe:xFant')
                data['emitente_ie'] = self._get_text(emit, 'nfe:IE')
                
                # Address
                ender_emit = emit.find('nfe:enderEmit', self.namespaces)
                if ender_emit is not None:
                    endereco_parts = []
                    
                    xLgr = self._get_text(ender_emit, 'nfe:xLgr')
                    nro = self._get_text(ender_emit, 'nfe:nro')
                    xBairro = self._get_text(ender_emit, 'nfe:xBairro')
                    
                    if xLgr:
                        endereco_parts.append(xLgr)
                    if nro:
                        endereco_parts.append(f"nº {nro}")
                    if xBairro:
                        endereco_parts.append(xBairro)
                    
                    data['emitente_endereco'] = ', '.join(endereco_parts)
                    data['emitente_municipio'] = self._get_text(ender_emit, 'nfe:xMun')
                    data['emitente_uf'] = self._get_text(ender_emit, 'nfe:UF')
                    data['emitente_cep'] = self._get_text(ender_emit, 'nfe:CEP')
        
        except Exception as e:
            logger.warning(f"Error extracting emitente data: {str(e)}")
        
        return data
    
    def _extract_destinatario(self, root):
        """Extract recipient data (DEST section)."""
        data = {}
        
        try:
            dest = root.find('.//nfe:dest', self.namespaces)
            if dest is not None:
                data['destinatario_cnpj'] = self._get_text(dest, 'nfe:CNPJ')
                data['destinatario_nome'] = self._get_text(dest, 'nfe:xNome')
                data['destinatario_ie'] = self._get_text(dest, 'nfe:IE')
                
                # Address
                ender_dest = dest.find('nfe:enderDest', self.namespaces)
                if ender_dest is not None:
                    endereco_parts = []
                    
                    xLgr = self._get_text(ender_dest, 'nfe:xLgr')
                    nro = self._get_text(ender_dest, 'nfe:nro')
                    xBairro = self._get_text(ender_dest, 'nfe:xBairro')
                    
                    if xLgr:
                        endereco_parts.append(xLgr)
                    if nro:
                        endereco_parts.append(f"nº {nro}")
                    if xBairro:
                        endereco_parts.append(xBairro)
                    
                    data['destinatario_endereco'] = ', '.join(endereco_parts)
                    data['destinatario_municipio'] = self._get_text(ender_dest, 'nfe:xMun')
                    data['destinatario_uf'] = self._get_text(ender_dest, 'nfe:UF')
                    data['destinatario_cep'] = self._get_text(ender_dest, 'nfe:CEP')
        
        except Exception as e:
            logger.warning(f"Error extracting destinatario data: {str(e)}")
        
        return data
    
    def _extract_totals(self, root):
        """Extract total values (TOTAL section)."""
        data = {}
        
        try:
            total = root.find('.//nfe:total', self.namespaces)
            if total is not None:
                icms_tot = total.find('nfe:ICMSTot', self.namespaces)
                if icms_tot is not None:
                    data['valor_total_produtos'] = self._get_decimal(icms_tot, 'nfe:vProd')
                    data['valor_total_nf'] = self._get_decimal(icms_tot, 'nfe:vNF')
                    data['valor_icms'] = self._get_decimal(icms_tot, 'nfe:vICMS')
                    data['valor_ipi'] = self._get_decimal(icms_tot, 'nfe:vIPI')
                    data['valor_pis'] = self._get_decimal(icms_tot, 'nfe:vPIS')
                    data['valor_cofins'] = self._get_decimal(icms_tot, 'nfe:vCOFINS')
                    data['valor_frete'] = self._get_decimal(icms_tot, 'nfe:vFrete')
                    data['valor_seguro'] = self._get_decimal(icms_tot, 'nfe:vSeg')
                    data['valor_desconto'] = self._get_decimal(icms_tot, 'nfe:vDesc')
                    data['valor_tributos'] = self._get_decimal(icms_tot, 'nfe:vTotTrib')
        
        except Exception as e:
            logger.warning(f"Error extracting totals data: {str(e)}")
        
        return data
    
    def _extract_transport(self, root):
        """Extract transport data (TRANSP section)."""
        data = {}
        
        try:
            transp = root.find('.//nfe:transp', self.namespaces)
            if transp is not None:
                mod_frete = self._get_text(transp, 'nfe:modFrete')
                frete_map = {
                    '0': 'Emitente',
                    '1': 'Destinatário',
                    '2': 'Terceiros',
                    '9': 'Sem frete'
                }
                data['modalidade_frete'] = frete_map.get(mod_frete, mod_frete)
                
                # Transportadora
                transporta = transp.find('nfe:transporta', self.namespaces)
                if transporta is not None:
                    data['transportadora_cnpj'] = self._get_text(transporta, 'nfe:CNPJ')
                    data['transportadora_nome'] = self._get_text(transporta, 'nfe:xNome')
        
        except Exception as e:
            logger.warning(f"Error extracting transport data: {str(e)}")
        
        return data
    
    def _extract_payment(self, root):
        """Extract payment data (PAG section)."""
        data = {}
        
        try:
            pag = root.find('.//nfe:pag', self.namespaces)
            if pag is not None:
                det_pag = pag.find('nfe:detPag', self.namespaces)
                if det_pag is not None:
                    t_pag = self._get_text(det_pag, 'nfe:tPag')
                    payment_map = {
                        '01': 'Dinheiro',
                        '02': 'Cheque',
                        '03': 'Cartão de Crédito',
                        '04': 'Cartão de Débito',
                        '05': 'Crédito Loja',
                        '10': 'Vale Alimentação',
                        '11': 'Vale Refeição',
                        '12': 'Vale Presente',
                        '13': 'Vale Combustível',
                        '15': 'Boleto Bancário',
                        '90': 'Sem pagamento',
                        '99': 'Outros'
                    }
                    data['forma_pagamento'] = payment_map.get(t_pag, t_pag)
        
        except Exception as e:
            logger.warning(f"Error extracting payment data: {str(e)}")
        
        return data
    
    def _extract_protocol(self, root):
        """Extract protocol data (PROTNFE section)."""
        data = {}
        
        try:
            prot_nfe = root.find('.//nfe:protNFe', self.namespaces)
            if prot_nfe is not None:
                inf_prot = prot_nfe.find('nfe:infProt', self.namespaces)
                if inf_prot is not None:
                    data['protocolo_autorizacao'] = self._get_text(inf_prot, 'nfe:nProt')
                    data['status_autorizacao'] = self._get_text(inf_prot, 'nfe:cStat')
        
        except Exception as e:
            logger.warning(f"Error extracting protocol data: {str(e)}")
        
        return data
    
    def _extract_items(self, root):
        """Extract items/products data (DET section)."""
        items = []
        
        try:
            det_elements = root.findall('.//nfe:det', self.namespaces)
            
            for det in det_elements:
                item = {}
                
                # Item number
                item['numero_item'] = det.get('nItem')
                
                # Product information
                prod = det.find('nfe:prod', self.namespaces)
                if prod is not None:
                    item['codigo_produto'] = self._get_text(prod, 'nfe:cProd')
                    item['descricao_produto'] = self._get_text(prod, 'nfe:xProd')
                    item['ncm'] = self._get_text(prod, 'nfe:NCM')
                    item['cfop'] = self._get_text(prod, 'nfe:CFOP')
                    item['unidade_comercial'] = self._get_text(prod, 'nfe:uCom')
                    item['quantidade_comercial'] = self._get_decimal(prod, 'nfe:qCom')
                    item['valor_unitario_comercial'] = self._get_decimal(prod, 'nfe:vUnCom')
                    item['valor_total_produto'] = self._get_decimal(prod, 'nfe:vProd')
                    item['unidade_tributavel'] = self._get_text(prod, 'nfe:uTrib')
                    item['quantidade_tributavel'] = self._get_decimal(prod, 'nfe:qTrib')
                    item['valor_unitario_tributavel'] = self._get_decimal(prod, 'nfe:vUnTrib')
                
                # Tax information
                imposto = det.find('nfe:imposto', self.namespaces)
                if imposto is not None:
                    # ICMS
                    icms = imposto.find('nfe:ICMS', self.namespaces)
                    if icms is not None:
                        # Find the specific ICMS group (ICMS00, ICMS10, etc.)
                        for icms_group in icms:
                            item['origem_mercadoria'] = self._get_text(icms_group, 'nfe:orig')
                            item['situacao_tributaria_icms'] = self._get_text(icms_group, 'nfe:CST')
                            item['base_calculo_icms'] = self._get_decimal(icms_group, 'nfe:vBC')
                            item['aliquota_icms'] = self._get_decimal(icms_group, 'nfe:pICMS')
                            item['valor_icms'] = self._get_decimal(icms_group, 'nfe:vICMS')
                            break
                    
                    # IPI
                    ipi = imposto.find('nfe:IPI', self.namespaces)
                    if ipi is not None:
                        for ipi_group in ipi:
                            if ipi_group.tag.endswith('IPINT') or ipi_group.tag.endswith('IPITrib'):
                                item['situacao_tributaria_ipi'] = self._get_text(ipi_group, 'nfe:CST')
                                item['valor_ipi'] = self._get_decimal(ipi_group, 'nfe:vIPI')
                                break
                    
                    # PIS
                    pis = imposto.find('nfe:PIS', self.namespaces)
                    if pis is not None:
                        for pis_group in pis:
                            item['situacao_tributaria_pis'] = self._get_text(pis_group, 'nfe:CST')
                            item['base_calculo_pis'] = self._get_decimal(pis_group, 'nfe:vBC')
                            item['aliquota_pis'] = self._get_decimal(pis_group, 'nfe:pPIS')
                            item['valor_pis'] = self._get_decimal(pis_group, 'nfe:vPIS')
                            break
                    
                    # COFINS
                    cofins = imposto.find('nfe:COFINS', self.namespaces)
                    if cofins is not None:
                        for cofins_group in cofins:
                            item['situacao_tributaria_cofins'] = self._get_text(cofins_group, 'nfe:CST')
                            item['base_calculo_cofins'] = self._get_decimal(cofins_group, 'nfe:vBC')
                            item['aliquota_cofins'] = self._get_decimal(cofins_group, 'nfe:pCOFINS')
                            item['valor_cofins'] = self._get_decimal(cofins_group, 'nfe:vCOFINS')
                            break
                
                items.append(item)
        
        except Exception as e:
            logger.warning(f"Error extracting items data: {str(e)}")
        
        return items
    
    def _get_text(self, element, xpath):
        """Get text content from XML element."""
        try:
            found = element.find(xpath, self.namespaces)
            return found.text if found is not None else None
        except:
            return None
    
    def _get_decimal(self, element, xpath):
        """Get decimal value from XML element."""
        try:
            text = self._get_text(element, xpath)
            return Decimal(text) if text else None
        except:
            return None
    
    def _parse_datetime(self, date_str):
        """Parse datetime string from NFe format."""
        try:
            # NFe datetime format: YYYY-MM-DDTHH:MM:SS-03:00
            # Remove timezone info for simplicity
            date_str = re.sub(r'[+-]\d{2}:\d{2}$', '', date_str)
            return datetime.fromisoformat(date_str)
        except:
            return None
