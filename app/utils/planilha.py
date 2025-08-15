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
        
        # Converte o arquivo para csv
        

        df = pd.read_excel(arquivo_baixado)

        # Normalização e limpeza dos dados
        logger.debug("Normalizando e limpando dados...")
        
        # Remove colunas completamente vazias
        df = df.dropna(axis=1, how='all')
        
        # Renomeia colunas para formato mais amigável
        df.columns = [
            str(col).strip().lower().replace(' ', '_').replace('/', '_').replace('-', '_')
            for col in df.columns
        ]
        

        df = corrigir_colunas(df)
        logger.debug("Colunas normalizadas e corrigidas")    
        # Substitui valores não compatíveis com JSON de forma mais robusta
        # Tratamento específico para cada tipo de valor problemático
        for col in df.select_dtypes(include=[np.number]).columns:
            # Para valores infinitos
            df.loc[df[col] == float('inf'), col] = np.nan
            df.loc[df[col] == float('-inf'), col] = np.nan
        
        # Para valores pd.NA e pd.NaT em todas as colunas
        df = df.fillna(np.nan)        
        
        # Retirar os dados cuja unidade orcamentaria é tecpar, gestão e fundo paraná
        # CORREÇÃO: usar o nome correto da coluna após corrigir_colunas
        if 'UNIDADE_ORCAMENTARIA' in df.columns:
            df = df[~df['UNIDADE_ORCAMENTARIA'].str.contains("GABINETE DO SECRETÁRIO|SUPERINTENDENCIA DE CIENCIA, TECNOLOGIA E ENSINO SUPERIOR|TECPAR|GESTÃO ADMINISTRATIVA|FUNDO PARANÁ|GABINETE DO SECRETARIO|DIRETORIA GERAL|FUNDO PARANA", na=False)]
        else:
            logger.warning("Coluna 'UNIDADE_ORCAMENTARIA' não encontrada, pulando filtro")
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

def corrigir_colunas(df):
    """
    Corrige a estrutura das colunas do CSV do Portal da Transparência.
    O CSV tem uma estrutura específica com subheaders nas primeiras linhas.
    """
    logger.debug(f"DataFrame original - shape: {df.shape}")
    logger.debug(f"Primeiras 5 linhas:\n{df.head()}")
    
    if len(df) < 2:
        logger.warning("DataFrame tem menos de 2 linhas, retornando sem alterações")
        return df
    
    # Mapear as colunas corretas baseado na estrutura do CSV
    novos_nomes = [
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
    
    # Ajustar para o número real de colunas
    num_colunas = len(df.columns)
    while len(novos_nomes) < num_colunas:
        novos_nomes.append(f"COLUNA_{len(novos_nomes)}")
    
    # Renomear as colunas
    df.columns = novos_nomes[:num_colunas]
    logger.debug(f"Colunas renomeadas para: {df.columns.tolist()}")
    
    # Identificar e remover linhas de cabeçalho/subheader
    # Procurar pela linha que contém "ATÉ MÊS" ou similar
    linhas_para_remover = []
    
    for idx in range(min(5, len(df))):  # Verificar apenas as primeiras 5 linhas
        linha = df.iloc[idx]
        # Verificar se a linha contém indicadores de cabeçalho
        linha_str = ' '.join([str(val) for val in linha.values if pd.notna(val)])
        
        if any(indicador in linha_str.upper() for indicador in [
            'ATÉ MÊS', 'NO MÊS', 'UNIDADE ORÇAMENTÁRIA', 'FUNÇÃO', 
            'GRUPO DE NATUREZA', 'ORIGEM DOS RECURSOS'
        ]):
            linhas_para_remover.append(idx)
            logger.debug(f"Linha {idx} marcada para remoção (cabeçalho): {linha_str[:100]}")
    
    # Remover linhas de cabeçalho identificadas
    if linhas_para_remover:
        df = df.drop(linhas_para_remover).reset_index(drop=True)
        logger.debug(f"Removidas {len(linhas_para_remover)} linhas de cabeçalho")
    
    # Remover linhas completamente vazias ou que são resumos/totais
    df_original_len = len(df)
    
    # Filtrar linhas vazias
    df = df.dropna(how='all')    
    
    linhas_removidas = df_original_len - len(df)
    if linhas_removidas > 0:
        logger.debug(f"Removidas {linhas_removidas} linhas vazias/totais")
    
    # Limpar e converter valores monetários
    colunas_monetarias = [col for col in df.columns if any(palavra in col for palavra in [
        'ORCAMENTO', 'DISPONIBILIDADE', 'EMPENHADO', 'LIQUIDADO', 'PAGO'
    ])]
    
    logger.debug(f"Colunas monetárias identificadas: {colunas_monetarias}")
    
    return df