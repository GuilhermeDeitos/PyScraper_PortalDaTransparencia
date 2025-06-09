"""
Utilitários para baixar e processar planilhas do Portal da Transparência.
"""
import os
import time
import pandas as pd
import numpy as np
import logging
from typing import List, Dict, Any, Optional
from selenium import webdriver
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from selenium.common.exceptions import TimeoutException

from app.utils.file_utils import (
    obter_arquivos_mais_recentes, 
    limpar_diretorio
)

logger = logging.getLogger(__name__)

def baixar_e_processar_planilha(driver: webdriver.Chrome, diretorio_download: str) -> Optional[List[Dict[str, Any]]]:
    """
    Baixa e processa a planilha de resultados do Portal da Transparência.
    
    Args:
        driver: Instância do navegador Chrome
        diretorio_download: Diretório onde a planilha será baixada
        
    Returns:
        Lista de dicionários com os dados processados, ou None em caso de erro
    """
    try:
        
        # Limpa quaisquer arquivos antigos para evitar confusão
        limpar_diretorio(diretorio_download)
        logger.debug(f"Diretório de download limpo: {diretorio_download}")
        
        # Tenta localizar o botão de download usando diferentes estratégias
        try:
            # Primeiro tenta encontrar o botão visualmente
            logger.debug("Procurando botão 'Visualizar em Planilha'...")
            botao = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.ID, "formPesquisa:btnVisualizarPlanilha"))
            )
            botao.click()
            logger.debug("Botão de download clicado via Selenium")
        except TimeoutException:
            # Se não encontrar, tenta via JavaScript
            logger.debug("Tentando clicar no botão via JavaScript...")
            driver.execute_script("""
                var botao = document.getElementById('formPesquisa:btnVisualizarPlanilha');
                if (botao) {
                    botao.click();
                } else {
                    // Tenta encontrar por seletor mais genérico
                    var botoes = document.querySelectorAll('button[id*="btnVisualizarPlanilha"], a[id*="btnVisualizarPlanilha"]');
                    if (botoes.length > 0) {
                        botoes[0].click();
                    } else {
                        throw new Error("Botão de download não encontrado");
                    }
                }
            """)
            logger.debug("Botão de download clicado via JavaScript")
        
        # Aguarda o download da planilha
        logger.info("Aguardando conclusão do download...")
        tempo_inicio = time.time()
        arquivo_baixado = None
        max_espera = 60  # segundos
        
        while time.time() - tempo_inicio < max_espera:
            # Verifica se há arquivos .xls no diretório
            arquivos_recentes = obter_arquivos_mais_recentes(diretorio_download, extensao=".xls")
            
            if arquivos_recentes:
                arquivo_baixado = arquivos_recentes[0]  # O mais recente
                
                # Verifica se o arquivo não está sendo gravado (tamanho estável)
                tamanho_inicial = os.path.getsize(arquivo_baixado)
                time.sleep(1)
                if os.path.getsize(arquivo_baixado) == tamanho_inicial:
                    logger.info(f"Download concluído em {time.time() - tempo_inicio:.2f} segundos")
                    break
            
            time.sleep(0.5)  # Pequena pausa para evitar uso excessivo de CPU
        
        if not arquivo_baixado:
            logger.error("Timeout: Nenhum arquivo Excel foi baixado")
            return None
        
        # Processa a planilha
        logger.info(f"Processando arquivo: {os.path.basename(arquivo_baixado)}")
        
        try:
            # Tenta ler com xlrd (compatível com formatos .xls antigos)
            df = pd.read_excel(arquivo_baixado, engine='xlrd')
            logger.debug("Arquivo processado com engine 'xlrd'")
        except Exception as e1:
            logger.warning(f"Erro ao processar com xlrd: {e1}, tentando openpyxl")
            try:
                # Tenta com openpyxl (para formatos .xlsx mais recentes)
                df = pd.read_excel(arquivo_baixado, engine='openpyxl')
                logger.debug("Arquivo processado com engine 'openpyxl'")
            except Exception as e2:
                logger.error(f"Falha ao processar arquivo com openpyxl: {e2}")
                raise
        
        # Normalização e limpeza dos dados
        logger.debug("Normalizando e limpando dados...")
        
        # Remove colunas completamente vazias
        df = df.dropna(axis=1, how='all')
        
        # Renomeia colunas para formato mais amigável
        df.columns = [
            str(col).strip().lower().replace(' ', '_').replace('/', '_').replace('-', '_')
            for col in df.columns
        ]
        
        # Substitui valores não compatíveis com JSON
        df = df.replace([float('inf'), float('-inf'), pd.NA, pd.NaT], np.nan)
        
        # Converte para lista de dicionários
        registros = df.to_dict(orient='records')
        
        # Limpeza final para compatibilidade com JSON
        for registro in registros:
            for chave, valor in list(registro.items()):
                # Trata valores NaN/None
                if isinstance(valor, float) and (np.isnan(valor) or np.isinf(valor)):
                    registro[chave] = None
                # Converte valores numpy para tipos Python nativos
                elif hasattr(valor, 'dtype') and isinstance(valor, np.generic):
                    registro[chave] = valor.item()
        
        logger.info(f"Processamento concluído: {len(registros)} registros obtidos")
        
        # Log de amostra dos dados (apenas em modo DEBUG)
        if logger.isEnabledFor(logging.DEBUG) and registros:
            primeiras_chaves = list(registros[0].keys())[:5]  # Primeiras 5 chaves
            amostra = {k: registros[0][k] for k in primeiras_chaves}
            logger.debug(f"Amostra dos dados: {amostra}")
        
        # Tenta excluir o arquivo após processamento
        try:
            os.remove(arquivo_baixado)
            logger.debug(f"Arquivo temporário excluído: {os.path.basename(arquivo_baixado)}")
        except Exception as e:
            logger.warning(f"Não foi possível excluir o arquivo: {e}")
        
        return registros
        
    except Exception as e:
        logger.error(f"Erro ao baixar ou processar planilha: {e}", exc_info=True)
        return None