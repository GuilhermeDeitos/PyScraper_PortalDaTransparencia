import pytest
import pandas as pd
import numpy as np
from app.utils.planilha import (
    normalizar_colunas,
    renomear_colunas,
    remover_linhas_cabecalho,
    limpar_valores_numericos,
    filtrar_unidades_orcamentarias,
    converter_para_json_compativel,
    corrigir_colunas,
    processar_dataframe,
    COLUNAS_PADRAO,
    UNIDADES_FILTRADAS
)

class TestNormalizarColunas:
    
    def test_remove_colunas_vazias(self):
        df = pd.DataFrame({
            'col1': [1, 2, 3],
            'col2': [np.nan, np.nan, np.nan],
            'col3': [4, 5, 6]
        })
        resultado = normalizar_colunas(df)
        assert len(resultado.columns) == 2
        assert 'col2' not in resultado.columns
    
    def test_normaliza_nomes_colunas(self):
        df = pd.DataFrame({
            'Nome Coluna': [1],
            'Outra/Coluna': [2],
            'Teste-Final': [3]
        })
        resultado = normalizar_colunas(df)
        assert 'nome_coluna' in resultado.columns
        assert 'outra_coluna' in resultado.columns
        assert 'teste_final' in resultado.columns

class TestRenomearColunas:
    
    def test_renomeia_com_nomes_padrao(self):
        df = pd.DataFrame([[1, 2, 3, 4, 5]])
        resultado = renomear_colunas(df)
        assert resultado.columns[0] == COLUNAS_PADRAO[0]
        assert resultado.columns[4] == COLUNAS_PADRAO[4]
    
    def test_adiciona_colunas_extras_quando_necessario(self):
        num_colunas = len(COLUNAS_PADRAO) + 3
        df = pd.DataFrame([[1] * num_colunas])
        resultado = renomear_colunas(df)
        assert len(resultado.columns) == num_colunas
        assert 'COLUNA_' in resultado.columns[-1]

class TestRemoverLinhasCabecalho:
    
    def test_remove_linhas_com_indicadores(self):
        df = pd.DataFrame({
            'col1': ['ATÉ MÊS', 'valor1', 'valor2'],
            'col2': ['NO MÊS', 'valor3', 'valor4']
        })
        resultado = remover_linhas_cabecalho(df)
        assert len(resultado) == 2
        assert 'ATÉ MÊS' not in resultado['col1'].values
    
    def test_mantem_dados_validos(self):
        df = pd.DataFrame({
            'col1': ['dados', 'normais'],
            'col2': ['aqui', 'também']
        })
        resultado = remover_linhas_cabecalho(df)
        assert len(resultado) == 2

class TestLimparValoresNumericos:
    
    def test_substitui_infinitos_por_nan(self):
        df = pd.DataFrame({
            'numeros': [1.0, float('inf'), float('-inf'), 5.0]
        })
        resultado = limpar_valores_numericos(df)
        assert pd.isna(resultado.iloc[1]['numeros'])
        assert pd.isna(resultado.iloc[2]['numeros'])
        assert resultado.iloc[0]['numeros'] == 1.0
    
    def test_mantem_valores_validos(self):
        df = pd.DataFrame({
            'numeros': [1.0, 2.0, 3.0],
            'texto': ['a', 'b', 'c']
        })
        resultado = limpar_valores_numericos(df)
        assert resultado['numeros'].sum() == 6.0

class TestFiltrarUnidadesOrcamentarias:
    
    def test_filtra_unidades_indesejadas(self):
        df = pd.DataFrame({
            'UNIDADE_ORCAMENTARIA': [
                'UNIDADE NORMAL',
                'GABINETE DO SECRETÁRIO',
                'OUTRA UNIDADE',
                'TECPAR'
            ]
        })
        resultado = filtrar_unidades_orcamentarias(df)
        assert len(resultado) == 2
        assert 'GABINETE DO SECRETÁRIO' not in resultado['UNIDADE_ORCAMENTARIA'].values
    
    def test_retorna_dataframe_se_coluna_inexistente(self):
        df = pd.DataFrame({'outra_coluna': [1, 2, 3]})
        resultado = filtrar_unidades_orcamentarias(df)
        assert len(resultado) == 3

class TestConverterParaJsonCompativel:
    
    def test_converte_nan_para_none(self):
        registros = [{'valor': np.nan}]
        resultado = converter_para_json_compativel(registros)
        assert resultado[0]['valor'] is None
    
    def test_converte_infinito_para_none(self):
        registros = [{'valor': float('inf')}]
        resultado = converter_para_json_compativel(registros)
        assert resultado[0]['valor'] is None
    
    def test_converte_numpy_types(self):
        registros = [{'valor': np.int64(42)}]
        resultado = converter_para_json_compativel(registros)
        assert isinstance(resultado[0]['valor'], int)
        assert resultado[0]['valor'] == 42

class TestCorrigirColunas:
    
    def test_retorna_dataframe_vazio_se_menos_de_2_linhas(self):
        df = pd.DataFrame([[1, 2, 3]])
        resultado = corrigir_colunas(df)
        assert len(resultado) <= 1
    
    def test_processa_dataframe_completo(self):
        df = pd.DataFrame([
            ['UNIDADE ORÇAMENTÁRIA', 'FUNÇÃO', 'GRUPO'],
            ['ATÉ MÊS', 'NO MÊS', 'TOTAL'],
            ['Unidade 1', 'Func 1', 100],
            ['Unidade 2', 'Func 2', 200]
        ])
        resultado = corrigir_colunas(df)
        assert len(resultado) == 2

class TestProcessarDataframe:
    
    def test_pipeline_completo(self):
        df = pd.DataFrame({
            'Unidade Orçamentária': ['UNIDADE TESTE', 'TECPAR'],
            'Função': ['Func 1', 'Func 2'],
            'Valor': [100.0, float('inf')]
        })
        
        resultado = processar_dataframe(df)
        
        assert isinstance(resultado, list)
        assert len(resultado) == 1
        assert resultado[0]['UNIDADE_ORCAMENTARIA'] == 'UNIDADE TESTE'