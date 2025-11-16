import os
import pandas as pd
import numpy as np
import logging
from typing import List, Dict, Any, Optional
from pathlib import Path

logger = logging.getLogger(__name__)

class ConsultaLocal:
    """
    Classe para buscar dados em planilhas locais pré-baixadas.
    As planilhas contêm dados de janeiro a dezembro para anos de 2002 a 2023.
    """
    
    def __init__(self):
        # Diretório base das planilhas (relativo ao diretório da classe)
        self.base_dir = Path(__file__).parent.parent.parent / "Dados_Despesas_2002-2023_Jan-Dez"
        self.anos_disponiveis = list(range(2002, 2024))  # 2002 a 2023
        
        # Verificar se o diretório existe
        if not self.base_dir.exists():
            logger.warning(f"Diretório de planilhas locais não encontrado: {self.base_dir}")
            self.base_dir_existe = False
        else:
            self.base_dir_existe = True
            arquivos = list(self.base_dir.glob("Despesas_*.xls"))
            logger.info(f"Encontrados {len(arquivos)} arquivos de planilha")
    
    def verificar_disponibilidade(self, ano: int, mes_inicio: int, mes_fim: int) -> bool:
      """
      Verifica se os dados estão disponíveis localmente para o período especificado.
      Dados locais são usados apenas se o período for de janeiro a dezembro.
      
      Args:
          ano: O ano da consulta
          mes_inicio: O mês de início (1-12)
          mes_fim: O mês de fim (1-12)
          
      Returns:
          True se os dados estiverem disponíveis localmente, False caso contrário
      """
      # Log para debug
      logger.debug(f"Verificando disponibilidade para ano={ano}, mês_início={mes_inicio}, mês_fim={mes_fim}")
      
      # Verifica se o diretório base existe
      if not hasattr(self, 'base_dir_existe') or not self.base_dir_existe:
          logger.debug(f"Diretório base não existe para ano {ano}")
          return False
          
      # Verifica se o ano está na faixa disponível
      if ano not in self.anos_disponiveis:
          logger.debug(f"Ano {ano} fora da faixa disponível {self.anos_disponiveis[0]}-{self.anos_disponiveis[-1]}")
          return False
          
      # Caso especial para o ano 2002, que estamos buscando com mês_início=2
      # Para 2002, usar dados locais apenas se for o ano completo
      if ano == 2002 and (mes_inicio != 1 or mes_fim != 12):
          logger.debug(f"Ano 2002 com período parcial não disponível localmente: {mes_inicio}-{mes_fim}")
          return False
          
      # Verifica se o período é de janeiro a dezembro (ano completo)
      if mes_inicio != 1 or mes_fim != 12:
          logger.debug(f"Período não é ano completo: {mes_inicio}-{mes_fim}")
          return False
          
      # Verifica se o arquivo existe
      arquivo = self.base_dir / f"Despesas_{ano}.xls"
      if not arquivo.exists():
          logger.debug(f"Arquivo não encontrado: {arquivo}")
          return False
      
      logger.debug(f"Dados locais disponíveis para ano {ano}")
      return True
    
    def obter_dados_ano(self, ano: int) -> Optional[List[Dict[str, Any]]]:
        """
        Obtém os dados de um ano específico a partir da planilha local.
        
        Args:
            ano: O ano para obter os dados
            
        Returns:
            Lista de dicionários com os dados ou None se não disponível
        """
        if not self.verificar_disponibilidade(ano, 1, 12):
            return None
            
        arquivo = self.base_dir / f"Despesas_{ano}.xls"
        logger.info(f"Processando planilha local para o ano {ano}: {arquivo}")
        
        try:
            # Lê o arquivo Excel
            df = pd.read_excel(arquivo)
            
            # Aplicar processamento similar ao do planilha.py
            df = self._processar_planilha(df, ano)
            
            # IMPORTANTE: Substituir inf e NaN ANTES de converter para dicionário
            # 1. Substituir infinitos por NaN primeiro
            df = df.replace([np.inf, -np.inf], np.nan)
            
            # 2. Converter para lista de dicionários (pandas converte NaN para None automaticamente)
            registros = df.to_dict(orient='records')
            
            # 3. Garantir que NaN seja None (em caso de conversão incompleta)
            for registro in registros:
                # Adicionar o ano validado a cada registro
                registro['_ano_validado'] = ano
                
                # Processar cada valor do registro
                for chave, valor in list(registro.items()):
                    # Converter tipos numpy para tipos Python nativos
                    if hasattr(valor, 'dtype') and isinstance(valor, np.generic):
                        registro[chave] = valor.item()
                    # Garantir que NaN/inf sejam None
                    elif isinstance(valor, float):
                        if np.isnan(valor) or np.isinf(valor):
                            registro[chave] = None
                
            logger.info(f"Dados locais para o ano {ano} processados: {len(registros)} registros obtidos")
            return registros
            
        except Exception as e:
            logger.error(f"Erro ao processar planilha local para o ano {ano}: {e}", exc_info=True)
            return None
    
    def _processar_planilha(self, df: pd.DataFrame, ano: int) -> pd.DataFrame:
        """
        Processa a planilha aplicando filtros e normalizações
        similar ao que é feito em planilha.py
        
        Args:
            df: DataFrame com os dados da planilha
            ano: O ano dos dados para rastreabilidade
            
        Returns:
            DataFrame processado
        """
        logger.debug(f"Processando planilha local para o ano {ano} - shape inicial: {df.shape}")
        
        df = df.dropna(axis=1, how='all')
        
        
        # Renomeia colunas para formato mais amigável
        df.columns = [
            str(col).strip().upper().replace(' ', '_').replace('/', '_').replace('-', '_')
            for col in df.columns
        ]
        
        
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
        
        # Renomear as colunas se necessário (verificar primeiro as existentes)
        if len(df.columns) == len(novos_nomes):
            df.columns = novos_nomes
        
        # Identificar e remover linhas de cabeçalho/subheader
        linhas_para_remover = []
        
        for idx in range(min(5, len(df))):  # Verificar apenas as primeiras 5 linhas
            linha = df.iloc[idx]
            linha_str = ' '.join([str(val).upper() for val in linha.values if pd.notna(val)])
            
            if any(indicador in linha_str for indicador in [
                'ATÉ MÊS', 'NO MÊS', 'UNIDADE ORÇAMENTÁRIA', 'FUNÇÃO', 
                'GRUPO DE NATUREZA', 'ORIGEM DOS RECURSOS'
            ]):
                linhas_para_remover.append(idx)
        
        # Remover linhas de cabeçalho identificadas
        if linhas_para_remover:
            df = df.drop(linhas_para_remover).reset_index(drop=True)
        
        # Remover linhas vazias ou totalizadoras
        df = df.dropna(how='all')
        
        # Filtrar apenas as universidades (remover TECPAR, GESTÃO, FUNDO PARANÁ, etc.)
        if 'UNIDADE_ORCAMENTARIA' in df.columns:
            df = df[~df['UNIDADE_ORCAMENTARIA'].astype(str).str.contains(
                "GABINETE DO SECRETÁRIO|SUPERINTENDENCIA DE CIENCIA, TECNOLOGIA E ENSINO SUPERIOR|"
                "TECPAR|GESTÃO ADMINISTRATIVA|FUNDO PARANÁ|GABINETE DO SECRETARIO|DIRETORIA GERAL|FUNDO PARANA", 
                na=False, case=False, regex=True
            )]
            
            # Filtrar apenas universidades estaduais
            df = df[df['UNIDADE_ORCAMENTARIA'].astype(str).str.contains(
                "UNIV|UEL|UEM|UEPG|UNICENTRO|UNIOESTE|UENP|UNESPAR",
                na=False, case=False, regex=True
            )]
        
        # Adicionar coluna MES com valor 12 para compatibilidade com o scraper
        # (dados anuais representam o acumulado até dezembro)
        df['MES'] = 12
        
        logger.debug(f"Planilha local para o ano {ano} processada - shape final: {df.shape}")
        return df