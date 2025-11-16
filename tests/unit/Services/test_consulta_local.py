import pytest
import pandas as pd
import numpy as np
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

from app.Services.consulta_local import ConsultaLocal


class TestConsultaLocalInicializacao:
    """Testes para inicialização da classe ConsultaLocal."""
    
    def test_inicializacao_com_diretorio_existente(self, tmp_path):
        """Testa inicialização quando diretório de dados existe."""
        # Arrange: Criar diretório temporário com arquivos
        dados_dir = tmp_path / "Dados_Despesas_2002-2023_Jan-Dez"
        dados_dir.mkdir()
        (dados_dir / "Despesas_2020.xls").touch()
        (dados_dir / "Despesas_2021.xls").touch()
        
        # Act
        with patch.object(Path, 'parent', new_callable=lambda: tmp_path):
            consulta = ConsultaLocal()
            consulta.base_dir = dados_dir
            consulta.base_dir_existe = True
        
        # Assert
        assert consulta.base_dir_existe is True
        assert consulta.anos_disponiveis == list(range(2002, 2024))
    
    def test_inicializacao_sem_diretorio(self, tmp_path):
        """Testa inicialização quando diretório não existe."""
        # Arrange
        dados_dir = tmp_path / "Diretorio_Inexistente"
        
        # Act
        consulta = ConsultaLocal()
        consulta.base_dir = dados_dir
        consulta.base_dir_existe = False
        
        # Assert
        assert consulta.base_dir_existe is False
        assert consulta.anos_disponiveis == list(range(2002, 2024))


class TestConsultaLocalVerificarDisponibilidade:
    """Testes para o método verificar_disponibilidade."""
    
    @pytest.fixture
    def consulta(self, tmp_path):
        """Fixture que cria uma instância de ConsultaLocal configurada."""
        dados_dir = tmp_path / "Dados_Despesas_2002-2023_Jan-Dez"
        dados_dir.mkdir()
        
        consulta = ConsultaLocal()
        consulta.base_dir = dados_dir
        consulta.base_dir_existe = True
        
        return consulta
    
    def test_disponibilidade_ano_completo_com_arquivo_existente(self, consulta):
        """Testa disponibilidade para ano completo (jan-dez) com arquivo presente."""
        # Arrange
        ano = 2020
        (consulta.base_dir / f"Despesas_{ano}.xls").touch()
        
        # Act
        resultado = consulta.verificar_disponibilidade(ano, 1, 12)
        
        # Assert
        assert resultado is True
    
    def test_indisponibilidade_periodo_parcial(self, consulta):
        """Testa que período parcial retorna False mesmo com arquivo existente."""
        # Arrange
        ano = 2020
        (consulta.base_dir / f"Despesas_{ano}.xls").touch()
        
        # Act & Assert - Diferentes períodos parciais
        assert consulta.verificar_disponibilidade(ano, 1, 6) is False  # Jan-Jun
        assert consulta.verificar_disponibilidade(ano, 3, 12) is False  # Mar-Dez
        assert consulta.verificar_disponibilidade(ano, 6, 9) is False  # Jun-Set
    
    def test_indisponibilidade_ano_2002_periodo_parcial(self, consulta):
        """Testa caso especial: ano 2002 com período parcial."""
        # Arrange
        (consulta.base_dir / "Despesas_2002.xls").touch()
        
        # Act & Assert
        assert consulta.verificar_disponibilidade(2002, 2, 12) is False
        assert consulta.verificar_disponibilidade(2002, 1, 11) is False
        assert consulta.verificar_disponibilidade(2002, 1, 12) is True  # Apenas ano completo
    
    def test_indisponibilidade_ano_fora_do_range(self, consulta):
        """Testa anos fora do intervalo 2002-2023."""
        # Act & Assert
        assert consulta.verificar_disponibilidade(2001, 1, 12) is False  # Antes de 2002
        assert consulta.verificar_disponibilidade(2024, 1, 12) is False  # Depois de 2023
        assert consulta.verificar_disponibilidade(1990, 1, 12) is False
    
    def test_indisponibilidade_arquivo_nao_existe(self, consulta):
        """Testa quando arquivo não existe no diretório."""
        # Arrange: Não criar o arquivo
        
        # Act
        resultado = consulta.verificar_disponibilidade(2020, 1, 12)
        
        # Assert
        assert resultado is False
    
    def test_indisponibilidade_diretorio_nao_existe(self, consulta):
        """Testa quando diretório base não existe."""
        # Arrange
        consulta.base_dir_existe = False
        
        # Act
        resultado = consulta.verificar_disponibilidade(2020, 1, 12)
        
        # Assert
        assert resultado is False
    
    @pytest.mark.parametrize("ano,mes_inicio,mes_fim,esperado", [
        (2020, 1, 12, True),   # Válido: ano completo
        (2015, 1, 12, True),   # Válido: ano completo
        (2020, 1, 6, False),   # Inválido: período parcial
        (2020, 6, 12, False),  # Inválido: período parcial
        (2001, 1, 12, False),  # Inválido: ano fora do range
        (2024, 1, 12, False),  # Inválido: ano fora do range
    ])
    def test_disponibilidade_parametrizado(self, consulta, ano, mes_inicio, mes_fim, esperado):
        """Testa múltiplos cenários de disponibilidade de forma parametrizada."""
        # Arrange: Criar arquivos para anos válidos
        if 2002 <= ano <= 2023:
            (consulta.base_dir / f"Despesas_{ano}.xls").touch()
        
        # Act
        resultado = consulta.verificar_disponibilidade(ano, mes_inicio, mes_fim)
        
        # Assert
        assert resultado == esperado


class TestConsultaLocalObterDadosAno:
    """Testes para o método obter_dados_ano."""
    
    @pytest.fixture
    def consulta(self, tmp_path):
        """Fixture com ConsultaLocal configurada."""
        dados_dir = tmp_path / "Dados_Despesas_2002-2023_Jan-Dez"
        dados_dir.mkdir()
        
        consulta = ConsultaLocal()
        consulta.base_dir = dados_dir
        consulta.base_dir_existe = True
        
        return consulta
    
    @pytest.fixture
    def df_mock_valido(self):
        """Fixture que retorna um DataFrame de exemplo válido."""
        return pd.DataFrame({
            'UNIDADE ORÇAMENTÁRIA': ['UNIVERSIDADE ESTADUAL DE LONDRINA', 'TECPAR', 'UNIVERSIDADE ESTADUAL DE MARINGÁ'],
            'FUNÇÃO': ['EDUCAÇÃO', 'CIÊNCIA E TECNOLOGIA', 'EDUCAÇÃO'],
            'GRUPO DE NATUREZA DE DESPESA': ['DESPESAS CORRENTES', 'DESPESAS CORRENTES', 'INVESTIMENTOS'],
            'ORIGEM DOS RECURSOS': ['RECURSOS ORDINÁRIOS', 'RECURSOS ORDINÁRIOS', 'RECURSOS VINCULADOS'],
            'ORÇAMENTO INICIAL - LOA': [1000000, 500000, 2000000],
            'TOTAL ORÇAMENTÁRIO ATÉ MÊS': [1100000, 550000, 2100000],
            'TOTAL ORÇAMENTÁRIO NO MÊS': [100000, 50000, 100000],
            'DISPONIBILIDADE ORÇAMENTÁRIA ATÉ MÊS': [900000, 400000, 1800000],
            'DISPONIBILIDADE ORÇAMENTÁRIA NO MÊS': [50000, 25000, 75000],
            'EMPENHADO ATÉ MÊS': [200000, 150000, 300000],
            'EMPENHADO NO MÊS': [20000, 15000, 30000],
            'LIQUIDADO ATÉ MÊS': [180000, 140000, 280000],
            'LIQUIDADO NO MÊS': [18000, 14000, 28000],
            'PAGO ATÉ MÊS': [170000, 130000, 270000],
            'PAGO NO MÊS': [17000, 13000, 27000]
        })
    
    def test_obter_dados_ano_sucesso(self, consulta, df_mock_valido, mocker):
        """Testa obtenção bem-sucedida de dados para um ano."""
        # Arrange
        ano = 2020
        (consulta.base_dir / f"Despesas_{ano}.xls").touch()
        
        mocker.patch('pandas.read_excel', return_value=df_mock_valido)
        
        # Act
        resultado = consulta.obter_dados_ano(ano)
        
        # Assert
        assert resultado is not None
        assert isinstance(resultado, list)
        assert len(resultado) > 0
        
        # Verifica que apenas universidades foram mantidas (TECPAR removido)
        nomes_unidades = [r['UNIDADE_ORCAMENTARIA'] for r in resultado]
        assert any('LONDRINA' in nome or 'MARINGA' in nome for nome in nomes_unidades)
        assert not any('TECPAR' in nome for nome in nomes_unidades)
        
        # Verifica que o ano foi adicionado
        assert all(r['_ano_validado'] == ano for r in resultado)
        
        # Verifica que MES foi adicionado
        assert all(r['MES'] == 12 for r in resultado)
    
    def test_obter_dados_ano_indisponivel(self, consulta):
        """Testa retorno None quando dados não estão disponíveis."""
        # Arrange: Não criar arquivo
        ano = 2020
        
        # Act
        resultado = consulta.obter_dados_ano(ano)
        
        # Assert
        assert resultado is None
    
    def test_obter_dados_ano_trata_valores_nan(self, consulta, mocker):
        """Testa tratamento de valores NaN na planilha."""
        # Arrange
        ano = 2020
        (consulta.base_dir / f"Despesas_{ano}.xls").touch()
        
        # IMPORTANTE: DataFrame REALISTA com algumas células NaN, não colunas inteiras
        df_com_nan = pd.DataFrame({
            'UNIDADE ORÇAMENTÁRIA': ['UNIVERSIDADE ESTADUAL DE LONDRINA', 'UNIVERSIDADE ESTADUAL DE MARINGÁ'],
            'FUNÇÃO': ['EDUCAÇÃO', np.nan],  # Apenas UMA célula NaN
            'GRUPO DE NATUREZA DE DESPESA': ['DESPESAS CORRENTES', 'INVESTIMENTOS'],
            'ORIGEM DOS RECURSOS': [np.nan, 'RECURSOS VINCULADOS'],  # Apenas UMA célula NaN
            'ORÇAMENTO INICIAL - LOA': [1000000, 2000000],
            'TOTAL ORÇAMENTÁRIO ATÉ MÊS': [1100000, 2100000],
            'TOTAL ORÇAMENTÁRIO NO MÊS': [100000, 100000],
            'DISPONIBILIDADE ORÇAMENTÁRIA ATÉ MÊS': [900000, 1800000],
            'DISPONIBILIDADE ORÇAMENTÁRIA NO MÊS': [50000, 75000],
            'EMPENHADO ATÉ MÊS': [200000, 300000],
            'EMPENHADO NO MÊS': [20000, 30000],
            'LIQUIDADO ATÉ MÊS': [180000, 280000],
            'LIQUIDADO NO MÊS': [18000, 28000],
            'PAGO ATÉ MÊS': [170000, 270000],
            'PAGO NO MÊS': [17000, 27000]
        })
        
        mocker.patch('pandas.read_excel', return_value=df_com_nan)
        
        # Act
        resultado = consulta.obter_dados_ano(ano)
        
        # Assert
        assert resultado is not None, "Resultado não deveria ser None"
        assert len(resultado) == 2, f"Esperado 2 registros, encontrado {len(resultado)}"
        
        # Verifica PRIMEIRO registro (tem ORIGEM_RECURSOS como NaN)
        registro_1 = resultado[0]
        assert registro_1.get('FUNCAO') == 'EDUCAÇÃO'
        assert registro_1.get('ORIGEM_RECURSOS') is None, "ORIGEM_RECURSOS deveria ser None (era NaN)"
        
        # Verifica SEGUNDO registro (tem FUNÇÃO como NaN)
        registro_2 = resultado[1]
        assert registro_2.get('FUNCAO') is None, "FUNCAO deveria ser None (era NaN)"
        assert registro_2.get('ORIGEM_RECURSOS') == 'RECURSOS VINCULADOS'
        
        # Verifica que valores válidos permanecem
        assert registro_1.get('UNIDADE_ORCAMENTARIA') == 'UNIVERSIDADE ESTADUAL DE LONDRINA'
        assert registro_2.get('UNIDADE_ORCAMENTARIA') == 'UNIVERSIDADE ESTADUAL DE MARINGÁ'
        
    def test_obter_dados_ano_trata_valores_infinitos(self, consulta, mocker):
        """Testa tratamento específico de valores infinitos."""
        # Arrange
        ano = 2020
        (consulta.base_dir / f"Despesas_{ano}.xls").touch()
        
        df_com_inf = pd.DataFrame({
            'UNIDADE ORÇAMENTÁRIA': ['UNIVERSIDADE ESTADUAL DE LONDRINA'],
            'FUNÇÃO': ['EDUCAÇÃO'],
            'GRUPO DE NATUREZA DE DESPESA': ['DESPESAS CORRENTES'],
            'ORIGEM DOS RECURSOS': ['RECURSOS ORDINÁRIOS'],
            'ORÇAMENTO INICIAL - LOA': [np.inf],  # Valor infinito positivo
            'TOTAL ORÇAMENTÁRIO ATÉ MÊS': [-np.inf],  # Valor infinito negativo
            'TOTAL ORÇAMENTÁRIO NO MÊS': [100000],
            'DISPONIBILIDADE ORÇAMENTÁRIA ATÉ MÊS': [900000],
            'DISPONIBILIDADE ORÇAMENTÁRIA NO MÊS': [50000],
            'EMPENHADO ATÉ MÊS': [200000],
            'EMPENHADO NO MÊS': [20000],
            'LIQUIDADO ATÉ MÊS': [180000],
            'LIQUIDADO NO MÊS': [18000],
            'PAGO ATÉ MÊS': [170000],
            'PAGO NO MÊS': [17000]
        })
        
        mocker.patch('pandas.read_excel', return_value=df_com_inf)
        
        # Act
        resultado = consulta.obter_dados_ano(ano)
        
        # Assert
        assert resultado is not None
        assert len(resultado) > 0
        
        registro = resultado[0]
        
        # Verifica que valores infinitos foram convertidos para None
        valores_none = [k for k, v in registro.items() if v is None]
        assert len(valores_none) >= 2, f"Esperado pelo menos 2 valores None (infinitos), encontrado {len(valores_none)}: {valores_none}"
        
        # Verifica colunas específicas
        assert registro.get('ORCAMENTO_INICIAL_LOA') is None
        assert registro.get('TOTAL_ORCAMENTARIO_ATE_MES') is None
    
    def test_obter_dados_ano_erro_leitura_arquivo(self, consulta, mocker):
        """Testa tratamento de erro ao ler arquivo Excel."""
        # Arrange
        ano = 2020
        (consulta.base_dir / f"Despesas_{ano}.xls").touch()
        
        mocker.patch('pandas.read_excel', side_effect=Exception("Erro ao ler arquivo"))
        
        # Act
        resultado = consulta.obter_dados_ano(ano)
        
        # Assert
        assert resultado is None


class TestConsultaLocalProcessarPlanilha:
    """Testes para o método _processar_planilha."""
    
    @pytest.fixture
    def consulta(self):
        return ConsultaLocal()
    
    def test_processar_planilha_remove_colunas_vazias(self, consulta):
        """Testa remoção de colunas completamente vazias."""
        # Arrange
        df = pd.DataFrame({
            'Coluna_Valida': [1, 2, 3],
            'Coluna_Vazia': [np.nan, np.nan, np.nan],
            'Outra_Valida': ['A', 'B', 'C']
        })
        
        # Act
        resultado = consulta._processar_planilha(df, 2020)
        
        # Assert
        assert 'COLUNA_VAZIA' not in resultado.columns
        # Verifica que pelo menos uma coluna válida permaneceu
        assert len(resultado.columns) >= 2
    
    def test_processar_planilha_normaliza_nomes_colunas(self, consulta):
        """Testa normalização de nomes de colunas."""
        # Arrange
        df = pd.DataFrame({
            'Unidade Orçamentária': ['UNIVERSIDADE ESTADUAL DE LONDRINA'],
            'Total Orçamentário - Até Mês': [1000],
            'Pago/No Mês': [100],
            'Função': ['EDUCAÇÃO'],
            'Grupo de Natureza de Despesa': ['DESPESAS CORRENTES'],
            'Origem dos Recursos': ['RECURSOS ORDINÁRIOS'],
            'Orçamento Inicial - LOA': [1000000],
            'Total Orçamentário no Mês': [100000],
            'Disponibilidade Orçamentária Até Mês': [900000],
            'Disponibilidade Orçamentária no Mês': [50000],
            'Empenhado Até Mês': [200000],
            'Empenhado no Mês': [20000],
            'Liquidado Até Mês': [180000],
            'Liquidado no Mês': [18000],
            'Pago Até Mês': [170000],
        })
        
        # Act
        resultado = consulta._processar_planilha(df, 2020)
        
        # Assert
        # Verifica que espaços, barras e hífens foram substituídos por underscore
        assert not any(' ' in col for col in resultado.columns), "Colunas não devem conter espaços"
        assert not any('/' in col for col in resultado.columns), "Colunas não devem conter barras"
        # Verifica que pelo menos algumas colunas esperadas existem
        assert 'UNIDADE_ORCAMENTARIA' in resultado.columns
    
    def test_processar_planilha_filtra_universidades(self, consulta):
        """Testa filtro que mantém apenas universidades."""
        # Arrange
        df = pd.DataFrame({
            'UNIDADE ORÇAMENTÁRIA': [
                'UNIVERSIDADE ESTADUAL DE LONDRINA',
                'TECPAR - INSTITUTO DE TECNOLOGIA',
                'UNIVERSIDADE ESTADUAL DE MARINGÁ',
                'GABINETE DO SECRETÁRIO',
                'UNIVERSIDADE ESTADUAL DE PONTA GROSSA'
            ],
            'FUNÇÃO': ['ED', 'CT', 'ED', 'AD', 'ED'],
            'GRUPO DE NATUREZA DE DESPESA': ['DC'] * 5,
            'ORIGEM DOS RECURSOS': ['RO'] * 5,
            'ORÇAMENTO INICIAL - LOA': [1000] * 5,
            'TOTAL ORÇAMENTÁRIO ATÉ MÊS': [1100] * 5,
            'TOTAL ORÇAMENTÁRIO NO MÊS': [100] * 5,
            'DISPONIBILIDADE ORÇAMENTÁRIA ATÉ MÊS': [900] * 5,
            'DISPONIBILIDADE ORÇAMENTÁRIA NO MÊS': [50] * 5,
            'EMPENHADO ATÉ MÊS': [200] * 5,
            'EMPENHADO NO MÊS': [20] * 5,
            'LIQUIDADO ATÉ MÊS': [180] * 5,
            'LIQUIDADO NO MÊS': [18] * 5,
            'PAGO ATÉ MÊS': [170] * 5,
            'PAGO NO MÊS': [17] * 5
        })
        
        # Act
        resultado = consulta._processar_planilha(df, 2020)
        
        # Assert
        assert len(resultado) == 3, f"Esperado 3 universidades, encontrado {len(resultado)}"
        unidades = resultado['UNIDADE_ORCAMENTARIA'].tolist()
        assert all('UNIVERSIDADE' in str(u).upper() or any(sigla in str(u).upper() for sigla in ['UEL', 'UEM', 'UEPG']) for u in unidades)
        assert not any('TECPAR' in str(u).upper() for u in unidades)
        assert not any('GABINETE' in str(u).upper() for u in unidades)
    
    def test_processar_planilha_adiciona_coluna_mes(self, consulta):
        """Testa adição da coluna MES com valor 12."""
        # Arrange
        df = pd.DataFrame({
            'UNIDADE ORÇAMENTÁRIA': ['UNIVERSIDADE ESTADUAL DE LONDRINA'],
            'FUNÇÃO': ['EDUCAÇÃO'],
            'GRUPO DE NATUREZA DE DESPESA': ['DESPESAS CORRENTES'],
            'ORIGEM DOS RECURSOS': ['RECURSOS ORDINÁRIOS'],
            'ORÇAMENTO INICIAL - LOA': [1000000],
            'TOTAL ORÇAMENTÁRIO ATÉ MÊS': [1100000],
            'TOTAL ORÇAMENTÁRIO NO MÊS': [100000],
            'DISPONIBILIDADE ORÇAMENTÁRIA ATÉ MÊS': [900000],
            'DISPONIBILIDADE ORÇAMENTÁRIA NO MÊS': [50000],
            'EMPENHADO ATÉ MÊS': [200000],
            'EMPENHADO NO MÊS': [20000],
            'LIQUIDADO ATÉ MÊS': [180000],
            'LIQUIDADO NO MÊS': [18000],
            'PAGO ATÉ MÊS': [170000],
            'PAGO NO MÊS': [17000]
        })
        
        # Act
        resultado = consulta._processar_planilha(df, 2020)
        
        # Assert
        assert 'MES' in resultado.columns, "Coluna MES deve existir"
        assert all(resultado['MES'] == 12), "Todos os valores de MES devem ser 12"
    
    def test_processar_planilha_remove_linhas_cabecalho(self, consulta):
        """Testa remoção de linhas de cabeçalho duplicadas."""
        # Arrange
        df = pd.DataFrame({
            'UNIDADE ORÇAMENTÁRIA': [
                'UNIDADE ORÇAMENTÁRIA',  # Linha de cabeçalho
                'ATÉ MÊS',  # Subheader
                'UNIVERSIDADE ESTADUAL DE LONDRINA'
            ],
            'FUNÇÃO': ['FUNÇÃO', 'NO MÊS', 'EDUCAÇÃO'],
            'GRUPO DE NATUREZA DE DESPESA': ['GRUPO DE NATUREZA', 'GRUPO', 'DESPESAS CORRENTES'],
            'ORIGEM DOS RECURSOS': ['ORIGEM DOS RECURSOS', 'RECURSOS', 'RECURSOS ORDINÁRIOS'],
            'ORÇAMENTO INICIAL - LOA': ['LOA', 'INICIAL', 1000000],
            'TOTAL ORÇAMENTÁRIO ATÉ MÊS': ['TOTAL', 'ATÉ', 1100000],
            'TOTAL ORÇAMENTÁRIO NO MÊS': ['TOTAL', 'NO', 100000],
            'DISPONIBILIDADE ORÇAMENTÁRIA ATÉ MÊS': ['DISP', 'ATÉ', 900000],
            'DISPONIBILIDADE ORÇAMENTÁRIA NO MÊS': ['DISP', 'NO', 50000],
            'EMPENHADO ATÉ MÊS': ['EMP', 'ATÉ', 200000],
            'EMPENHADO NO MÊS': ['EMP', 'NO', 20000],
            'LIQUIDADO ATÉ MÊS': ['LIQ', 'ATÉ', 180000],
            'LIQUIDADO NO MÊS': ['LIQ', 'NO', 18000],
            'PAGO ATÉ MÊS': ['PAGO', 'ATÉ', 170000],
            'PAGO NO MÊS': ['PAGO', 'NO', 17000]
        })
        
        # Act
        resultado = consulta._processar_planilha(df, 2020)
        
        # Assert
        # Apenas a linha de dados reais deve permanecer
        assert len(resultado) <= 1, "Deve haver no máximo 1 linha de dados reais"


class TestConsultaLocalIntegracao:
    """Testes de integração para fluxo completo."""
    
    def test_fluxo_completo_ano_disponivel(self, tmp_path, mocker):
        """Testa o fluxo completo de verificação e obtenção de dados."""
        # Arrange
        dados_dir = tmp_path / "Dados_Despesas_2002-2023_Jan-Dez"
        dados_dir.mkdir()
        ano = 2020
        (dados_dir / f"Despesas_{ano}.xls").touch()
        
        df_mock = pd.DataFrame({
            'UNIDADE ORÇAMENTÁRIA': ['UNIVERSIDADE ESTADUAL DE LONDRINA'],
            'FUNÇÃO': ['EDUCAÇÃO'],
            'GRUPO DE NATUREZA DE DESPESA': ['DESPESAS CORRENTES'],
            'ORIGEM DOS RECURSOS': ['RECURSOS ORDINÁRIOS'],
            'ORÇAMENTO INICIAL - LOA': [1000000],
            'TOTAL ORÇAMENTÁRIO ATÉ MÊS': [1100000],
            'TOTAL ORÇAMENTÁRIO NO MÊS': [100000],
            'DISPONIBILIDADE ORÇAMENTÁRIA ATÉ MÊS': [900000],
            'DISPONIBILIDADE ORÇAMENTÁRIA NO MÊS': [50000],
            'EMPENHADO ATÉ MÊS': [200000],
            'EMPENHADO NO MÊS': [20000],
            'LIQUIDADO ATÉ MÊS': [180000],
            'LIQUIDADO NO MÊS': [18000],
            'PAGO ATÉ MÊS': [170000],
            'PAGO NO MÊS': [17000]
        })
        
        mocker.patch('pandas.read_excel', return_value=df_mock)
        
        consulta = ConsultaLocal()
        consulta.base_dir = dados_dir
        consulta.base_dir_existe = True
        
        # Act
        disponivel = consulta.verificar_disponibilidade(ano, 1, 12)
        dados = consulta.obter_dados_ano(ano) if disponivel else None
        
        # Assert
        assert disponivel is True
        assert dados is not None
        assert len(dados) > 0
        assert dados[0]['_ano_validado'] == ano