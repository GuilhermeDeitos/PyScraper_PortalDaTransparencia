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
from app.utils.file_utils import obter_arquivos_mais_recentes, limpar_diretorio
import threading

logger = logging.getLogger(__name__)
file_operation_lock = threading.RLock()

TIMEOUT_DOWNLOAD = 60
COLUNAS_PADRAO = [
    "UNIDADE_ORCAMENTARIA",
    "FUNCAO", 
    "GRUPO_NATUREZA_DESPESA",
    "ORIGEM_RECURSOS",
    "ORCAMENTO_INICIAL_LOA",
    "TOTAL_ORCAMENTARIO_ATE_MES",
    "TOTAL_ORCAMENTARIO_NO_MES", 
    "DISPONIBILIDADE_ORCAMENTARIA_ATE_MES",
    "DISPONIBILIDADE_ORCAMENTARIA_NO_MES",
    "EMPENHADO_ATE_MES",
    "EMPENHADO_NO_MES",
    "LIQUIDADO_ATE_MES",
    "LIQUIDADO_NO_MES",
    "PAGO_ATE_MES",
    "PAGO_NO_MES"
]

UNIDADES_FILTRADAS = [
    "GABINETE DO SECRETÁRIO",
    "SUPERINTENDENCIA DE CIENCIA, TECNOLOGIA E ENSINO SUPERIOR",
    "TECPAR",
    "GESTÃO ADMINISTRATIVA",
    "FUNDO PARANÁ",
    "GABINETE DO SECRETARIO",
    "DIRETORIA GERAL",
    "FUNDO PARANA"
]

def clicar_botao_download(driver: webdriver.Chrome, log_prefix: str) -> None:
    """Clica no botão de download da planilha."""
    try:
        logger.debug(f"{log_prefix} Procurando botão 'Visualizar em Planilha'...")
        botao = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.ID, "formPesquisa:btnVisualizarPlanilha"))
        )
        botao.click()
        logger.debug(f"{log_prefix} Botão de download clicado via Selenium")
    except TimeoutException:
        logger.debug(f"{log_prefix} Tentando clicar no botão via JavaScript...")
        driver.execute_script("""
            var botao = document.getElementById('formPesquisa:btnVisualizarPlanilha');
            if (botao) {
                botao.click();
            } else {
                var botoes = document.querySelectorAll('button[id*="btnVisualizarPlanilha"], a[id*="btnVisualizarPlanilha"]');
                if (botoes.length > 0) {
                    botoes[0].click();
                } else {
                    throw new Error("Botão de download não encontrado");
                }
            }
        """)
        logger.debug(f"{log_prefix} Botão de download clicado via JavaScript")

def aguardar_download(diretorio: str, log_prefix: str, timeout: int = TIMEOUT_DOWNLOAD) -> Optional[str]:
    """Aguarda o download do arquivo e retorna o caminho."""
    logger.info(f"{log_prefix} Aguardando conclusão do download...")
    tempo_inicio = time.time()
    
    while time.time() - tempo_inicio < timeout:
        with file_operation_lock:
            arquivos_recentes = obter_arquivos_mais_recentes(diretorio, extensao=".xls")
            
            if arquivos_recentes:
                arquivo = arquivos_recentes[0]
                
                try:
                    tamanho_inicial = os.path.getsize(arquivo)
                    time.sleep(1)
                    tamanho_atual = os.path.getsize(arquivo)
                    
                    if tamanho_atual == tamanho_inicial and tamanho_atual > 0:
                        logger.info(f"{log_prefix} Download concluído em {time.time() - tempo_inicio:.2f}s")
                        return arquivo
                except:
                    continue
        
        time.sleep(0.5)
    
    logger.error(f"{log_prefix} Timeout: Nenhum arquivo Excel foi baixado")
    return None

def normalizar_colunas(df: pd.DataFrame) -> pd.DataFrame:
    """Normaliza os nomes das colunas."""
    df = df.dropna(axis=1, how='all')
    df.columns = [
        str(col).strip().lower().replace(' ', '_').replace('/', '_').replace('-', '_')
        for col in df.columns
    ]
    return df

def renomear_colunas(df: pd.DataFrame) -> pd.DataFrame:
    """Renomeia as colunas para o padrão esperado."""
    num_colunas = len(df.columns)
    novos_nomes = COLUNAS_PADRAO.copy()
    
    while len(novos_nomes) < num_colunas:
        novos_nomes.append(f"COLUNA_{len(novos_nomes)}")
    
    df.columns = novos_nomes[:num_colunas]
    logger.debug(f"Colunas renomeadas: {df.columns.tolist()}")
    return df

def remover_linhas_cabecalho(df: pd.DataFrame) -> pd.DataFrame:
    """Remove linhas de cabeçalho duplicadas."""
    indicadores_cabecalho = [
        'ATÉ MÊS', 'NO MÊS', 'UNIDADE ORÇAMENTÁRIA', 'FUNÇÃO', 
        'GRUPO DE NATUREZA', 'ORIGEM DOS RECURSOS'
    ]
    
    linhas_para_remover = []
    
    for idx in range(min(5, len(df))):
        linha_str = ' '.join([str(val) for val in df.iloc[idx].values if pd.notna(val)])
        
        if any(ind in linha_str.upper() for ind in indicadores_cabecalho):
            linhas_para_remover.append(idx)
            logger.debug(f"Linha {idx} marcada para remoção: {linha_str[:100]}")
    
    if linhas_para_remover:
        df = df.drop(linhas_para_remover).reset_index(drop=True)
        logger.debug(f"Removidas {len(linhas_para_remover)} linhas de cabeçalho")
    
    return df

def limpar_valores_numericos(df: pd.DataFrame) -> pd.DataFrame:
    """Limpa valores infinitos e NaN."""
    for col in df.select_dtypes(include=[np.number]).columns:
        df.loc[df[col] == float('inf'), col] = np.nan
        df.loc[df[col] == float('-inf'), col] = np.nan
    
    df = df.fillna(np.nan)
    return df

def filtrar_unidades_orcamentarias(df: pd.DataFrame) -> pd.DataFrame:
    """Filtra unidades orçamentárias não desejadas."""
    if 'UNIDADE_ORCAMENTARIA' not in df.columns:
        logger.warning("Coluna 'UNIDADE_ORCAMENTARIA' não encontrada, pulando filtro")
        return df
    
    pattern = "|".join(UNIDADES_FILTRADAS)
    df_filtrado = df[~df['UNIDADE_ORCAMENTARIA'].str.contains(pattern, na=False)]
    
    linhas_removidas = len(df) - len(df_filtrado)
    if linhas_removidas > 0:
        logger.debug(f"Removidas {linhas_removidas} linhas de unidades filtradas")
    
    return df_filtrado

def converter_para_json_compativel(registros: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Converte os registros para tipos compatíveis com JSON."""
    for registro in registros:
        for chave, valor in list(registro.items()):
            if isinstance(valor, float) and (np.isnan(valor) or np.isinf(valor)):
                registro[chave] = None
            elif hasattr(valor, 'dtype') and isinstance(valor, np.generic):
                registro[chave] = valor.item()
    
    return registros

def corrigir_colunas(df: pd.DataFrame) -> pd.DataFrame:
    """Corrige a estrutura das colunas do DataFrame."""
    logger.debug(f"DataFrame original - shape: {df.shape}")
    
    if len(df) < 2:
        logger.warning("DataFrame tem menos de 2 linhas")
        return df
    
    df = renomear_colunas(df)
    df = remover_linhas_cabecalho(df)
    df = df.dropna(how='all')
    
    linhas_removidas = len(df)
    logger.debug(f"DataFrame após limpeza: {len(df)} linhas")
    
    return df

def processar_dataframe(df: pd.DataFrame) -> List[Dict[str, Any]]:
    """Processa o DataFrame completo e retorna lista de registros."""
    df = normalizar_colunas(df)
    df = corrigir_colunas(df)
    df = limpar_valores_numericos(df)
    df = filtrar_unidades_orcamentarias(df)
    
    registros = df.to_dict(orient='records')
    registros = converter_para_json_compativel(registros)
    
    return registros

def baixar_e_processar_planilha(
    driver: webdriver.Chrome, 
    diretorio_download: str, 
    scraper_id: str = None
) -> Optional[List[Dict[str, Any]]]:
    """
    Baixa e processa a planilha com isolamento thread-safe.
    
    Args:
        driver: Instância do WebDriver
        diretorio_download: Caminho do diretório de download
        scraper_id: ID único do scraper para logging
        
    Returns:
        Lista de dicionários com os dados ou None se falhar
    """
    thread_id = threading.get_ident()
    log_prefix = f"[Scraper {scraper_id}][Thread {thread_id}]" if scraper_id else f"[Thread {thread_id}]"
    
    logger.info(f"{log_prefix} Iniciando download em: {diretorio_download}")
    
    try:
        if not os.path.exists(diretorio_download):
            raise Exception(f"Diretório não existe: {diretorio_download}")
        
        with file_operation_lock:
            limpar_diretorio(diretorio_download)
        
        clicar_botao_download(driver, log_prefix)
        arquivo_baixado = aguardar_download(diretorio_download, log_prefix)
        
        if not arquivo_baixado:
            return None

        with file_operation_lock:
            logger.info(f"{log_prefix} Processando: {os.path.basename(arquivo_baixado)}")
            
            try:
                df = pd.read_excel(arquivo_baixado)
                registros = processar_dataframe(df)
                
                logger.info(f"{log_prefix} Processamento concluído: {len(registros)} registros")
                
                if logger.isEnabledFor(logging.DEBUG) and registros:
                    primeiras_chaves = list(registros[0].keys())[:5]
                    amostra = {k: registros[0][k] for k in primeiras_chaves}
                    logger.debug(f"{log_prefix} Amostra: {amostra}")
                
                try:
                    os.remove(arquivo_baixado)
                    logger.debug(f"{log_prefix} Arquivo temporário excluído")
                except Exception as e:
                    logger.warning(f"{log_prefix} Não foi possível excluir arquivo: {e}")
                
                return registros
                
            except Exception as e:
                logger.error(f"{log_prefix} Erro ao processar Excel: {e}", exc_info=True)
                try:
                    if os.path.exists(arquivo_baixado):
                        os.remove(arquivo_baixado)
                except:
                    pass
                raise
        
    except Exception as e:
        logger.error(f"{log_prefix} Erro ao baixar/processar planilha: {e}", exc_info=True)
        return None