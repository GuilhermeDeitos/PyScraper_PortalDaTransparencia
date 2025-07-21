import asyncio
import os
import time
import pandas as pd
import numpy as np
import logging
from typing import List, Dict, Any, Optional
from pathlib import Path
from playwright.async_api import Page, TimeoutError as PlaywrightTimeoutError

from app.utils.file_utils import (
    obter_arquivos_mais_recentes, 
    limpar_diretorio
)

logger = logging.getLogger(__name__)

async def baixar_e_processar_planilha_playwright(page: Page, download_dir: str) -> Optional[List[Dict[str, Any]]]:
    """
    Baixa e processa a planilha de dados usando Playwright com API nativa de downloads.
    
    Args:
        page: Objeto Page do Playwright
        download_dir: Diretório para salvar downloads
        
    Returns:
        Lista de dicionários com os dados da planilha ou None em caso de erro
    """
    logger.info(f"=== INÍCIO DA FUNÇÃO DOWNLOAD PLAYWRIGHT ===")
    logger.info(f"Diretório de download configurado: {download_dir}")
    
    try:
        # Limpa quaisquer arquivos antigos para evitar confusão
        logger.info("Iniciando limpeza do diretório de download...")
        await asyncio.get_event_loop().run_in_executor(None, limpar_diretorio, download_dir)
        logger.info(f"Diretório de download limpo: {download_dir}")
        
        # Aguarda a página carregar completamente
        logger.info("Aguardando página carregar...")
        await page.wait_for_load_state('networkidle')        
        # Aguarda especificamente pelos componentes PrimeFaces carregarem
        try:
            await page.wait_for_function("window.PrimeFaces !== undefined", timeout=10000)
            logger.info("PrimeFaces carregado com sucesso")
        except Exception as e:
            logger.warning(f"PrimeFaces pode não ter carregado completamente: {e}")

        # Aguarda o botão aparecer e estar habilitado
        logger.info("Aguardando botão de download aparecer...")
        await page.wait_for_selector("button[id='formPesquisa:btnVisualizarPlanilha']", 
                                   state='visible', timeout=15000)
        
        async with page.expect_download(timeout=60000) as download_info:
            # Clica no botão para iniciar o download
            await page.click("button[id='formPesquisa:btnVisualizarPlanilha']")
            logger.info("Clique no botão de download realizado")
        
        # Aguarda o download completar
        download = await download_info.value
        logger.info(f"Download iniciado: {download.suggested_filename}")
        
        # Define o caminho para salvar o arquivo
        arquivo_destino = os.path.join(download_dir, download.suggested_filename)
        
        # Salva o arquivo no diretório especificado
        await download.save_as(arquivo_destino)
        logger.info(f"Arquivo salvo em: {arquivo_destino}")
        
        # Verifica se o arquivo foi salvo corretamente
        if not os.path.exists(arquivo_destino) or os.path.getsize(arquivo_destino) == 0:
            logger.error("Arquivo não foi baixado corretamente")
            return None
        
        logger.info(f"Download concluído com sucesso: {os.path.basename(arquivo_destino)}")
        
        # Processa a planilha em uma thread separada para não bloquear
        registros = await asyncio.get_event_loop().run_in_executor(
            None, _processar_planilha_sync, arquivo_destino
        )
        
        logger.info(f"=== FIM DA FUNÇÃO - {len(registros) if registros else 0} registros processados ===")
        return registros
        
    except Exception as e:
        logger.error(f"Erro geral na função de download: {e}", exc_info=True)
        
        # Tira screenshot para debug em caso de erro
        try:
            screenshot_path = os.path.join(download_dir, "debug_download_error.png")
            await page.screenshot(path=screenshot_path, full_page=True)
            logger.info(f"Screenshot de erro salvo em: {screenshot_path}")
        except Exception as screenshot_error:
            logger.error(f"Erro ao tirar screenshot: {screenshot_error}")
            return None

        
        # Se chegou aqui, o botão foi clicado
        logger.info("=== BOTÃO CLICADO COM SUCESSO ===")
        logger.info("Aguardando download iniciar...")
        
        # Aguarda o download da planilha
        logger.info("Aguardando conclusão do download...")
        tempo_inicio = time.time()
        arquivo_baixado = None
        max_espera = 60  # segundos
        # Exibir o diretório de download
        
        while time.time() - tempo_inicio < max_espera:
            # Verifica se há arquivos .xls no diretório
            logger.debug(f"Verificando arquivos .xls no diretório: {download_dir}")
            #Obter se tem arquivo .xls no diretório de download
            arquivos_recentes = obter_arquivos_mais_recentes(download_dir, extensao='.xls')
            
            if arquivos_recentes:
                arquivo_baixado = arquivos_recentes[0]  # O mais recente
                logger.info(f"Arquivo encontrado: {arquivo_baixado}")
                
                # Verifica se o arquivo não está sendo gravado (tamanho estável)
                tamanho_inicial = os.path.getsize(arquivo_baixado)
                if os.path.getsize(arquivo_baixado) == tamanho_inicial:
                    logger.info(f"Download concluído em {time.time() - tempo_inicio:.2f} segundos")
                    break
                    
        if not arquivo_baixado:
            logger.error("Timeout: Nenhum arquivo Excel foi baixado")
            return None
        
        # Processa a planilha
        logger.info(f"Processando arquivo: {os.path.basename(arquivo_baixado)}")
        
        # Processa a planilha em uma thread separada para não bloquear
        registros = await asyncio.get_event_loop().run_in_executor(
            None, _processar_planilha_sync, arquivo_baixado
        )
        
        logger.info(f"=== FIM DA FUNÇÃO - {len(registros) if registros else 0} registros processados ===")
        return registros
        
    except Exception as e:
        logger.error(f"Erro geral na função: {e}", exc_info=True)
        return None

def _processar_planilha_sync(arquivo_baixado: str) -> Optional[List[Dict[str, Any]]]:
    """
    Processa a planilha de forma síncrona (executada em thread separada).
    
    Args:
        arquivo_baixado: Caminho para o arquivo baixado
        
    Returns:
        Lista de dicionários com os dados processados, ou None em caso de erro
    """
    try:
        # Leitura do arquivo Excel
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
        
        df = corrigir_colunas_playwright(df)
        logger.debug("Colunas normalizadas e corrigidas")
        
        if len(df) > 0:
            df = df.drop(0)
            
        # Substitui valores não compatíveis com JSON
        df = df.replace([float('inf'), float('-inf'), pd.NA, pd.NaT], np.nan)
        
        # Retirar os dados cuja unidade orçamentária é tecpar, gestão e fundo paraná
        if 'UNIDADE_ORÇAMENTÁRIA' in df.columns:
            df = df[~df['UNIDADE_ORÇAMENTÁRIA'].str.contains(
                "45.70 - SECRETARIA DE ESTADO DA CIÊNCIA, TECNOLO / INSTITUTO DE TECNOLOGIA DO PARANÁ – TECPAR|"
                "45.04 - SECRETARIA DE ESTADO DA CIÊNCIA, TECNOLO / GESTÃO ADMINISTRATIVA|"
                "45.60 - SECRETARIA DE ESTADO DA CIÊNCIA, TECNOLO / FUNDO PARANÁ", 
                na=False
            )]
        
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
        logger.error(f"Erro ao processar planilha: {e}", exc_info=True)
        return None

def corrigir_colunas_playwright(df):
    """
    Corrige nomes de colunas tratando subheaders:
    - Substitui colunas "unnamed" com subheader "NO MÊS" pelo nome da coluna anterior + "_no_mes"
    - Adiciona "_ate_mes" nas colunas com subheader "ATÉ MÊS"
    - Converte todos os nomes para maiúsculas
    """
    nova_estrutura = {}
    coluna_anterior = None
    
    # Primeiro, extrair os nomes das colunas e seus valores de subheader
    colunas = df.columns.tolist()
    subheaders = df.iloc[0].tolist() if len(df) > 0 else [None] * len(colunas)
    
    # Mapear para o novo formato
    for i, (coluna, subheader) in enumerate(zip(colunas, subheaders)):
        # Verificar se é uma coluna unnamed
        if 'unnamed' in str(coluna).lower():
            novo_nome = f"{coluna_anterior}_no_mes"
            nova_estrutura[coluna] = novo_nome
        else:
            # Tratamento especial para a coluna "pago_(r$)"
            if "pago_(r$)" in str(coluna).lower() and "no_mes" not in str(coluna).lower():
                novo_nome = f"{coluna}_ate_mes"
                nova_estrutura[coluna] = novo_nome
            # Para colunas nomeadas com "ATÉ MÊS", adicionar sufixo
            elif isinstance(subheader, str) and subheader == 'ATÉ MÊS':
                novo_nome = f"{coluna}_ate_mes"
                nova_estrutura[coluna] = novo_nome
            else:
                nova_estrutura[coluna] = coluna
            
            # Armazenar nome da coluna para uso com unnamed seguintes
            coluna_anterior = coluna
    
    # Renomear colunas no DataFrame
    df = df.rename(columns=nova_estrutura)
    
    # Converter todos os nomes para maiúsculas
    df.columns = [str(col).upper() for col in df.columns]
    
    return df

async def processar_planilha_excel_async(file_path: str) -> Optional[List[Dict[str, Any]]]:
    """
    Processa um arquivo Excel de forma assíncrona.
    
    Args:
        file_path: Caminho para o arquivo Excel
        
    Returns:
        Lista de dicionários com os dados processados
    """
    try:
        logger.info(f"Processando arquivo Excel: {file_path}")
        
        # Executa o processamento em uma thread separada para não bloquear
        loop = asyncio.get_event_loop()
        dados = await loop.run_in_executor(None, _processar_planilha_sync, file_path)
        
        logger.info(f"Processamento concluído: {len(dados) if dados else 0} registros")
        return dados
        
    except Exception as e:
        logger.error(f"Erro ao processar planilha Excel: {e}")
        return None
