import pytest
import threading
import time
from datetime import datetime
from unittest.mock import Mock, patch

from app.Repositories.consulta_repo import ConsultaRepository


class TestConsultaRepositoryInicializacao:
    """Testes para inicialização do repositório."""
    
    def test_inicializacao_padrao(self):
        """Testa que o repositório inicia com estado limpo."""
        # Arrange & Act
        repo = ConsultaRepository()
        
        # Assert
        assert repo.consultas == {}
        assert repo.lock is not None
        assert isinstance(repo.lock, type(threading.Lock()))


class TestConsultaRepositoryIniciarConsulta:
    """Testes para o método iniciar_consulta."""
    
    @pytest.fixture
    def repo(self):
        return ConsultaRepository()
    
    def test_iniciar_consulta_ano_unico(self, repo):
        """Testa inicialização de consulta para um único ano."""
        # Arrange
        id_consulta = "test_001"
        anos_range = (2023, 2023)
        
        # Act
        repo.iniciar_consulta(id_consulta, anos_range, mes_inicio=1, mes_fim=12)
        
        # Assert
        assert id_consulta in repo.consultas
        consulta = repo.consultas[id_consulta]
        
        assert consulta["status"] == "processando"
        assert consulta["anos_pendentes"] == {2023}
        assert consulta["anos_concluidos"] == set()
        assert consulta["total_registros"] == 0
        assert consulta["mes_inicio"] == 1
        assert consulta["mes_fim"] == 12
        assert "iniciado_em" in consulta
        assert consulta["dados_por_ano"] == {}
        assert consulta["resumo_por_ano"] == {}
    
    def test_iniciar_consulta_multiplos_anos(self, repo):
        """Testa inicialização de consulta para múltiplos anos."""
        # Arrange
        id_consulta = "test_002"
        anos_range = (2020, 2023)
        
        # Act
        repo.iniciar_consulta(id_consulta, anos_range, mes_inicio=1, mes_fim=12)
        
        # Assert
        consulta = repo.consultas[id_consulta]
        assert consulta["anos_pendentes"] == {2020, 2021, 2022, 2023}
        assert len(consulta["anos_pendentes"]) == 4
    
    def test_iniciar_consulta_sem_parametros_mes(self, repo):
        """Testa inicialização sem especificar meses."""
        # Arrange
        id_consulta = "test_003"
        anos_range = (2023, 2023)
        
        # Act
        repo.iniciar_consulta(id_consulta, anos_range)
        
        # Assert
        consulta = repo.consultas[id_consulta]
        assert consulta["mes_inicio"] is None
        assert consulta["mes_fim"] is None


class TestConsultaRepositoryAdicionarResultadosAno:
    """Testes para o método adicionar_resultados_ano."""
    
    @pytest.fixture
    def repo_com_consulta(self):
        repo = ConsultaRepository()
        repo.iniciar_consulta("test_001", (2023, 2023), 1, 12)
        return repo
    
    @pytest.fixture
    def dados_mock(self):
        return [
            {
                "UNIDADE_ORCAMENTARIA": "UEL",
                "FUNCAO": "EDUCAÇÃO",
                "GRUPO_NATUREZA_DESPESA": "DESPESAS CORRENTES",
                "ORIGEM_DOS_RECURSOS": "RECURSOS ORDINÁRIOS",
                "ORÇAMENTO_INICIAL___LOA_(R$)": "1.000.000,00",
                "EMPENHADO_(R$)_ATE_MES": "500.000,00"
            },
            {
                "UNIDADE_ORCAMENTARIA": "UEM",
                "FUNCAO": "EDUCAÇÃO",
                "GRUPO_NATUREZA_DESPESA": "INVESTIMENTOS",
                "ORIGEM_DOS_RECURSOS": "RECURSOS VINCULADOS",
                "ORÇAMENTO_INICIAL___LOA_(R$)": "2.000.000,00",
                "EMPENHADO_(R$)_ATE_MES": "1.000.000,00"
            }
        ]
    
    def test_adicionar_resultados_ano_com_dados(self, repo_com_consulta, dados_mock):
        """Testa adição de resultados com dados válidos."""
        # Arrange
        id_consulta = "test_001"
        ano = 2023
        
        # Act
        repo_com_consulta.adicionar_resultados_ano(
            id_consulta, ano, dados_mock, mes_inicio=1, mes_fim=12
        )
        
        # Assert
        consulta = repo_com_consulta.consultas[id_consulta]
        
        assert str(ano) in consulta["dados_por_ano"]
        assert consulta["dados_por_ano"][str(ano)]["dados"] == dados_mock
        assert consulta["dados_por_ano"][str(ano)]["total_registros"] == 2
        assert consulta["dados_por_ano"][str(ano)]["mes_inicio"] == 1
        assert consulta["dados_por_ano"][str(ano)]["mes_fim"] == 12
        assert "processado_em" in consulta["dados_por_ano"][str(ano)]
        
        # Verifica que o ano foi movido de pendente para concluído
        assert ano not in consulta["anos_pendentes"]
        assert ano in consulta["anos_concluidos"]
        
        # Verifica total de registros
        assert consulta["total_registros"] == 2
        
        # Verifica que o resumo foi gerado
        assert str(ano) in consulta["resumo_por_ano"]
    
    def test_adicionar_resultados_ano_sem_dados(self, repo_com_consulta):
        """Testa adição de resultados com lista vazia."""
        # Arrange
        id_consulta = "test_001"
        ano = 2023
        
        # Act
        repo_com_consulta.adicionar_resultados_ano(
            id_consulta, ano, [], mes_inicio=1, mes_fim=12
        )
        
        # Assert
        consulta = repo_com_consulta.consultas[id_consulta]
        
        assert consulta["dados_por_ano"][str(ano)]["dados"] == []
        assert consulta["dados_por_ano"][str(ano)]["total_registros"] == 0
        assert consulta["total_registros"] == 0
        
        # Verifica que o resumo indica sem dados
        assert consulta["resumo_por_ano"][str(ano)]["sem_dados"] is True
    
    def test_adicionar_resultados_multiplos_anos(self, repo_com_consulta, dados_mock):
        """Testa adição de resultados para múltiplos anos."""
        # Arrange
        id_consulta = "test_001"
        repo_com_consulta.consultas[id_consulta]["anos_pendentes"] = {2022, 2023}
        
        # Act
        repo_com_consulta.adicionar_resultados_ano(id_consulta, 2022, dados_mock, 1, 12)
        repo_com_consulta.adicionar_resultados_ano(id_consulta, 2023, dados_mock, 1, 12)
        
        # Assert
        consulta = repo_com_consulta.consultas[id_consulta]
        
        assert "2022" in consulta["dados_por_ano"]
        assert "2023" in consulta["dados_por_ano"]
        assert consulta["total_registros"] == 4  # 2 registros * 2 anos
        assert len(consulta["anos_concluidos"]) == 2
        assert len(consulta["anos_pendentes"]) == 0
    
    def test_adicionar_resultados_consulta_inexistente(self, repo_com_consulta):
        """Testa adicionar resultados para consulta que não existe."""
        # Arrange
        id_inexistente = "inexistente"
        
        # Act (não deve levantar erro, apenas não fazer nada)
        repo_com_consulta.adicionar_resultados_ano(
            id_inexistente, 2023, [], 1, 12
        )
        
        # Assert
        assert id_inexistente not in repo_com_consulta.consultas


class TestConsultaRepositoryAtualizarStatus:
    """Testes para o método atualizar_status_processando."""
    
    @pytest.fixture
    def repo_com_consulta(self):
        repo = ConsultaRepository()
        repo.iniciar_consulta("test_001", (2023, 2023), 1, 12)
        return repo
    
    def test_atualizar_status_processando(self, repo_com_consulta):
        """Testa atualização de status durante processamento."""
        # Arrange
        id_consulta = "test_001"
        nova_mensagem = "Processando ano 2023..."
        
        # Act
        repo_com_consulta.atualizar_status_processando(id_consulta, nova_mensagem)
        
        # Assert
        consulta = repo_com_consulta.consultas[id_consulta]
        assert consulta["mensagem"] == nova_mensagem
        assert "ultima_atualizacao" in consulta
    
    def test_atualizar_status_consulta_inexistente(self, repo_com_consulta):
        """Testa atualização para consulta inexistente."""
        # Act (não deve levantar erro)
        repo_com_consulta.atualizar_status_processando(
            "inexistente", "teste"
        )
        
        # Assert
        assert "inexistente" not in repo_com_consulta.consultas


class TestConsultaRepositoryRegistrarErro:
    """Testes para registro de erros."""
    
    @pytest.fixture
    def repo_com_consulta(self):
        repo = ConsultaRepository()
        repo.iniciar_consulta("test_001", (2023, 2023), 1, 12)
        return repo
    
    def test_registrar_erro_ano(self, repo_com_consulta):
        """Testa registro de erro para um ano específico."""
        # Arrange
        id_consulta = "test_001"
        ano = 2023
        mensagem_erro = "Timeout ao buscar dados"
        
        # Act
        repo_com_consulta.registrar_erro_ano(id_consulta, ano, mensagem_erro)
        
        # Assert
        consulta = repo_com_consulta.consultas[id_consulta]
        
        assert "erros_por_ano" in consulta
        assert str(ano) in consulta["erros_por_ano"]
        assert consulta["erros_por_ano"][str(ano)]["erro"] == mensagem_erro
        assert "ocorrido_em" in consulta["erros_por_ano"][str(ano)]
        
        # Verifica que o ano foi marcado como concluído mesmo com erro
        assert ano not in consulta["anos_pendentes"]
        assert ano in consulta["anos_concluidos"]
        
        # Verifica que dados vazios foram registrados
        assert str(ano) in consulta["dados_por_ano"]
        assert consulta["dados_por_ano"][str(ano)]["dados"] == []
        assert "erro" in consulta["dados_por_ano"][str(ano)]
    
    def test_registrar_erro_consulta(self, repo_com_consulta):
        """Testa registro de erro geral da consulta."""
        # Arrange
        id_consulta = "test_001"
        mensagem_erro = "Erro crítico no sistema"
        
        # Act
        repo_com_consulta.registrar_erro_consulta(id_consulta, mensagem_erro)
        
        # Assert
        consulta = repo_com_consulta.consultas[id_consulta]
        
        assert consulta["status"] == "erro"
        assert consulta["erro_geral"] == mensagem_erro
        assert "erro_em" in consulta

class TestConsultaRepositoryFinalizarConsulta:
    """Testes para o método finalizar_consulta."""
    
    @pytest.fixture
    def repo_com_dados(self):
        repo = ConsultaRepository()
        repo.iniciar_consulta("test_001", (2023, 2023), 1, 12)
        
        dados = [
            {
                "UNIDADE_ORÇAMENTÁRIA": "UEL",
                "ORÇAMENTO_INICIAL___LOA_(R$)": "1.000.000,00",
                "EMPENHADO_(R$)_ATE_MES": "500.000,00"
            }
        ]
        
        repo.adicionar_resultados_ano("test_001", 2023, dados, 1, 12)
        return repo
    
    def test_finalizar_consulta_sucesso(self, repo_com_dados):
        """Testa finalização bem-sucedida de consulta."""
        # Arrange
        id_consulta = "test_001"
        
        # Act
        repo_com_dados.finalizar_consulta(id_consulta, status="concluido")
        
        # Assert
        consulta = repo_com_dados.consultas[id_consulta]
        
        assert consulta["status"] == "concluido"
        assert "concluido_em" in consulta
        assert "resumo" in consulta
    
    def test_finalizar_consulta_cancelada(self, repo_com_dados):
        """Testa finalização de consulta cancelada."""
        # Arrange
        id_consulta = "test_001"
        
        # Act
        repo_com_dados.finalizar_consulta(id_consulta, status="cancelada")
        
        # Assert
        consulta = repo_com_dados.consultas[id_consulta]
        assert consulta["status"] == "cancelada"
    
    def test_finalizar_consulta_com_anos_pendentes(self, repo_com_dados):
        """Testa que finalização NÃO ocorre com anos pendentes."""
        # Arrange
        id_consulta = "test_001"
        repo_com_dados.consultas[id_consulta]["anos_pendentes"].add(2024)
        
        # Status inicial
        status_inicial = repo_com_dados.consultas[id_consulta]["status"]
        
        # Act
        repo_com_dados.finalizar_consulta(id_consulta, status="concluido")
        
        # Assert - NÃO deve finalizar
        consulta = repo_com_dados.consultas[id_consulta]
        assert consulta["status"] == status_inicial  # Status não mudou
        assert "concluido_em" not in consulta  # Não foi marcado como concluído
        assert 2024 in consulta["anos_pendentes"]  # Ano ainda está pendente
    
    def test_finalizar_consulta_sem_dados_completos(self, repo_com_dados):
        """Testa que finalização NÃO ocorre se faltam dados de anos."""
        # Arrange
        id_consulta = "test_001"
        
        # Adicionar mais anos como concluídos mas SEM dados
        repo_com_dados.consultas[id_consulta]["anos_concluidos"].add(2024)
        # dados_por_ano tem apenas 2023, mas anos_concluidos tem 2023 e 2024
        
        status_inicial = repo_com_dados.consultas[id_consulta]["status"]
        
        # Act
        repo_com_dados.finalizar_consulta(id_consulta, status="concluido")
        
        # Assert - NÃO deve finalizar
        consulta = repo_com_dados.consultas[id_consulta]
        assert consulta["status"] == status_inicial  # Status não mudou
        assert "concluido_em" not in consulta  # Não foi marcado como concluído
    
    def test_finalizar_consulta_todos_anos_processados(self, repo_com_dados):
        """Testa finalização quando TODOS os anos foram processados."""
        # Arrange
        id_consulta = "test_001"
        
        # Garantir que anos_pendentes está vazio e dados_por_ano tem todos os anos
        repo_com_dados.consultas[id_consulta]["anos_pendentes"] = set()
        
        # Verificar que temos dados para todos os anos concluídos
        anos_concluidos = repo_com_dados.consultas[id_consulta]["anos_concluidos"]
        dados_por_ano = repo_com_dados.consultas[id_consulta]["dados_por_ano"]
        
        assert len(dados_por_ano) == len(anos_concluidos), "Deve ter dados para todos os anos"
        
        # Act
        repo_com_dados.finalizar_consulta(id_consulta, status="concluido")
        
        # Assert - DEVE finalizar
        consulta = repo_com_dados.consultas[id_consulta]
        assert consulta["status"] == "concluido"
        assert "concluido_em" in consulta
        assert "resumo" in consulta
    
    def test_finalizar_consulta_inexistente(self, repo_com_dados):
        """Testa finalização de consulta inexistente."""
        # Act (não deve levantar erro)
        repo_com_dados.finalizar_consulta("inexistente", status="concluido")
        
        # Assert
        assert "inexistente" not in repo_com_dados.consultas


class TestConsultaRepositoryObterConsulta:
    """Testes para o método obter_consulta."""
    
    @pytest.fixture
    def repo_com_cenarios(self):
        repo = ConsultaRepository()
        
        # Consulta concluída
        repo.iniciar_consulta("concluida", (2023, 2023), 1, 12)
        repo.adicionar_resultados_ano("concluida", 2023, [{"teste": "dados"}], 1, 12)
        repo.finalizar_consulta("concluida", status="concluido")
        
        # Consulta processando
        repo.iniciar_consulta("processando", (2023, 2023), 1, 12)
        
        # Consulta com erro
        repo.iniciar_consulta("erro", (2023, 2023), 1, 12)
        repo.registrar_erro_consulta("erro", "Erro simulado")
        
        return repo
    
    def test_obter_consulta_concluida(self, repo_com_cenarios):
        """Testa obtenção de consulta concluída - SEM dados_por_ano."""
        # Act
        resultado = repo_com_cenarios.obter_consulta("concluida")
        
        # Assert
        assert resultado["status"] == "concluido"
        assert "total_registros" in resultado
        assert "anos_processados" in resultado
        assert "iniciado_em" in resultado
        assert "periodo_consulta" in resultado
        assert "dados_ja_enviados" in resultado
        assert resultado["dados_ja_enviados"] is False
        
        # PRINCIPAL: Dados NÃO devem estar presentes
        assert "dados_por_ano" not in resultado
        assert "dados" not in resultado
    
    def test_obter_consulta_processando(self, repo_com_cenarios):
        """Testa obtenção de consulta em processamento."""
        # Act
        resultado = repo_com_cenarios.obter_consulta("processando")
        
        # Assert
        assert resultado["status"] == "processando"
        assert "mensagem" in resultado
        assert "anos_concluidos" in resultado
        assert "anos_pendentes" in resultado
        assert "dados_parciais_por_ano" in resultado
        assert "total_registros_ate_agora" in resultado
    
    def test_obter_consulta_com_erro(self, repo_com_cenarios):
        """Testa obtenção de consulta com erro."""
        # Act
        resultado = repo_com_cenarios.obter_consulta("erro")
        
        # Assert
        assert resultado["status"] == "erro"
        assert "mensagem" in resultado
        assert "erro_geral" in resultado
        assert "erro_em" in resultado
    
    def test_obter_consulta_inexistente(self, repo_com_cenarios):
        """Testa obtenção de consulta que não existe."""
        # Act
        resultado = repo_com_cenarios.obter_consulta("inexistente")
        
        # Assert
        assert "error" in resultado
        assert resultado["error"] == "Consulta não encontrada"


class TestConsultaRepositoryObterConsulta:
    """Testes para o método obter_consulta."""
    
    @pytest.fixture
    def repo_com_cenarios(self):
        repo = ConsultaRepository()
        
        # Consulta concluída
        repo.iniciar_consulta("concluida", (2023, 2023), 1, 12)
        repo.adicionar_resultados_ano("concluida", 2023, [{"teste": "dados"}], 1, 12)
        repo.finalizar_consulta("concluida", status="concluido")
        
        # Consulta processando
        repo.iniciar_consulta("processando", (2023, 2023), 1, 12)
        
        # Consulta com erro
        repo.iniciar_consulta("erro", (2023, 2023), 1, 12)
        repo.registrar_erro_consulta("erro", "Erro simulado")
        
        return repo
    
    def test_obter_consulta_concluida(self, repo_com_cenarios):
        """Testa obtenção de consulta concluída - COM dados_por_ano."""
        # Act
        resultado = repo_com_cenarios.obter_consulta("concluida")
        
        # Assert
        assert resultado["status"] == "concluido"
        assert "total_registros" in resultado
        assert "anos_processados" in resultado
        assert "iniciado_em" in resultado
        assert "periodo_consulta" in resultado
        assert "dados_ja_enviados" in resultado
        assert resultado["dados_ja_enviados"] is False
        
        # PRINCIPAL: Dados DEVEM estar presentes para evitar race condition
        assert "dados_por_ano" in resultado
        assert "2023" in resultado["dados_por_ano"]
    
    def test_obter_consulta_processando(self, repo_com_cenarios):
        """Testa obtenção de consulta em processamento."""
        # Act
        resultado = repo_com_cenarios.obter_consulta("processando")
        
        # Assert
        assert resultado["status"] == "processando"
        assert "mensagem" in resultado
        assert "anos_concluidos" in resultado
        assert "anos_pendentes" in resultado
        assert "dados_parciais_por_ano" in resultado
        assert "total_registros_ate_agora" in resultado
    
    def test_obter_consulta_com_erro(self, repo_com_cenarios):
        """Testa obtenção de consulta com erro."""
        # Act
        resultado = repo_com_cenarios.obter_consulta("erro")
        
        # Assert
        assert resultado["status"] == "erro"
        assert "mensagem" in resultado
        assert "erro_geral" in resultado
        assert "erro_em" in resultado
    
    def test_obter_consulta_inexistente(self, repo_com_cenarios):
        """Testa obtenção de consulta que não existe."""
        # Act
        resultado = repo_com_cenarios.obter_consulta("inexistente")
        
        # Assert
        assert "error" in resultado
        assert resultado["error"] == "Consulta não encontrada"


class TestConsultaRepositoryGerarResumo:
    """Testes para métodos de geração de resumos."""
    
    @pytest.fixture
    def repo(self):
        return ConsultaRepository()
    
    @pytest.fixture
    def dados_resumo(self):
        return [
            {
                "UNIDADE_ORÇAMENTÁRIA": "UEL",
                "FUNÇÃO": "EDUCAÇÃO",
                "ORIGEM_DOS_RECURSOS": "ORDINÁRIOS",
                "ORÇAMENTO_INICIAL___LOA_(R$)": "1.000.000,00",
                "EMPENHADO_(R$)_ATE_MES": "500.000,00",
                "LIQUIDADO_(R$)_ATE_MES": "400.000,00",
                "PAGO_(R$)_ATE_MES": "350.000,00"
            },
            {
                "UNIDADE_ORÇAMENTÁRIA": "UEM",
                "FUNÇÃO": "EDUCAÇÃO",
                "ORIGEM_DOS_RECURSOS": "VINCULADOS",
                "ORÇAMENTO_INICIAL___LOA_(R$)": "2.000.000,00",
                "EMPENHADO_(R$)_ATE_MES": "1.000.000,00",
                "LIQUIDADO_(R$)_ATE_MES": "900.000,00",
                "PAGO_(R$)_ATE_MES": "850.000,00"
            }
        ]
    
    def test_gerar_resumo_ano_com_dados(self, repo, dados_resumo):
        """Testa geração de resumo para um ano com dados."""
        # Act
        resumo = repo._gerar_resumo_ano(dados_resumo)
        
        # Assert
        assert resumo["total_registros"] == 2
        assert "valores_totais" in resumo
        assert "unidades_orcamentarias" in resumo
        assert "funcoes" in resumo
        assert "origens_recursos" in resumo
        
        # Verifica listas únicas
        assert len(resumo["unidades_orcamentarias"]) == 2
        assert "UEL" in resumo["unidades_orcamentarias"]
        assert "UEM" in resumo["unidades_orcamentarias"]
        
        # Verifica valores totais
        assert "ORÇAMENTO_INICIAL___LOA_(R$)" in resumo["valores_totais"]
        assert resumo["valores_totais"]["ORÇAMENTO_INICIAL___LOA_(R$)"] == 3000000.0
    
    def test_gerar_resumo_ano_vazio(self, repo):
        """Testa geração de resumo para ano sem dados."""
        # Act
        resumo = repo._gerar_resumo_ano([])
        
        # Assert
        assert resumo["total_registros"] == 0
        assert resumo["sem_dados"] is True
    
    def test_gerar_resumo_consolidado(self, repo):
        """Testa geração de resumo consolidado de múltiplos anos."""
        # Arrange
        consulta = {
            "total_registros": 4,
            "mes_inicio": 1,
            "mes_fim": 12,
            "dados_por_ano": {
                "2022": {
                    "dados": [
                        {
                            "ORÇAMENTO_INICIAL___LOA_(R$)": "1.000.000,00",
                            "EMPENHADO_(R$)_ATE_MES": "500.000,00"
                        }
                    ]
                },
                "2023": {
                    "dados": [
                        {
                            "ORÇAMENTO_INICIAL___LOA_(R$)": "2.000.000,00",
                            "EMPENHADO_(R$)_ATE_MES": "1.000.000,00"
                        }
                    ]
                }
            }
        }
        
        # Act
        resumo = repo._gerar_resumo_consolidado(consulta)
        
        # Assert
        assert resumo["total_registros"] == 4
        assert resumo["anos_processados"] == [2022, 2023]
        assert "valores_consolidados" in resumo
        assert "distribuicao_por_ano" in resumo
        assert resumo["periodo_total"]["anos_abrangidos"] == 2



class TestConsultaRepositoryConverterValor:
    """Testes para o método de conversão de valores monetários."""
    
    @pytest.fixture
    def repo(self):
        return ConsultaRepository()
    
    @pytest.mark.parametrize("entrada, esperado", [
        ("1.000.000,00", 1000000.0),
        ("500.000,50", 500000.5),
        ("1.234,56", 1234.56),
        ("0,00", 0.0),
        ("", 0.0),
        ("-", 0.0),
        (None, 0.0),
        ("100", 100.0),
        ("1000", 1000.0),
    ])
    def test_converter_valor_brasileiro_para_float(self, repo, entrada, esperado):
        """Testa conversão de valores em formato brasileiro para float."""
        # Act
        resultado = repo._converter_valor_brasileiro_para_float(entrada)
        
        # Assert
        assert resultado == esperado
    
    def test_converter_valor_com_espacos(self, repo):
        """Testa conversão de valor com espaços."""
        # Act
        resultado = repo._converter_valor_brasileiro_para_float(" 1.000,00 ")
        
        # Assert
        assert resultado == 1000.0


class TestConsultaRepositoryAdicionarMetadados:
    """Testes para o método adicionar_metadados_ano."""
    
    @pytest.fixture
    def repo_com_consulta(self):
        repo = ConsultaRepository()
        repo.iniciar_consulta("test_001", (2023, 2023), 1, 12)
        return repo
    
    def test_adicionar_metadados_ano(self, repo_com_consulta):
        """Testa adição de metadados para um ano."""
        # Arrange
        id_consulta = "test_001"
        ano = 2023
        metadados = {
            "fonte": "local",
            "tempo_processamento": 1.5,
            "estrategia": "otimizada"
        }
        
        # Act
        repo_com_consulta.adicionar_metadados_ano(id_consulta, ano, metadados)
        
        # Assert
        consulta = repo_com_consulta.consultas[id_consulta]
        assert "metadados_anos" in consulta
        assert str(ano) in consulta["metadados_anos"]
        assert consulta["metadados_anos"][str(ano)]["fonte"] == "local"
        assert consulta["metadados_anos"][str(ano)]["tempo_processamento"] == 1.5
    
    def test_adicionar_metadados_multiplas_vezes(self, repo_com_consulta):
        """Testa adição de metadados múltiplas vezes (update)."""
        # Arrange
        id_consulta = "test_001"
        ano = 2023
        
        # Act
        repo_com_consulta.adicionar_metadados_ano(id_consulta, ano, {"campo1": "valor1"})
        repo_com_consulta.adicionar_metadados_ano(id_consulta, ano, {"campo2": "valor2"})
        
        # Assert
        metadados = repo_com_consulta.consultas[id_consulta]["metadados_anos"][str(ano)]
        assert "campo1" in metadados
        assert "campo2" in metadados


class TestConsultaRepositoryThreadSafety:
    """Testes para verificar thread-safety."""
    
    def test_operacoes_concorrentes(self):
        """Testa múltiplas threads acessando o repositório simultaneamente."""
        # Arrange
        repo = ConsultaRepository()
        repo.iniciar_consulta("test_concurrent", (2020, 2023), 1, 12)
        
        resultados = []
        
        def adicionar_dados(ano):
            dados = [{"teste": f"ano_{ano}"}]
            repo.adicionar_resultados_ano("test_concurrent", ano, dados, 1, 12)
            resultados.append(ano)
        
        # Act
        threads = []
        for ano in [2020, 2021, 2022, 2023]:
            t = threading.Thread(target=adicionar_dados, args=(ano,))
            threads.append(t)
            t.start()
        
        for t in threads:
            t.join()
        
        # Assert
        consulta = repo.consultas["test_concurrent"]
        assert len(consulta["dados_por_ano"]) == 4
        assert consulta["total_registros"] == 4
        assert len(resultados) == 4
    
    def test_leitura_durante_escrita(self):
        """Testa leitura de consulta enquanto está sendo atualizada."""
        # Arrange
        repo = ConsultaRepository()
        repo.iniciar_consulta("test_read_write", (2023, 2023), 1, 12)
        
        leituras_realizadas = []
        
        def escrever():
            for i in range(10):
                repo.atualizar_status_processando(
                    "test_read_write", 
                    f"Processando {i}"
                )
                time.sleep(0.01)
        
        def ler():
            for _ in range(10):
                resultado = repo.obter_consulta("test_read_write")
                leituras_realizadas.append(resultado)
                time.sleep(0.01)
        
        # Act
        t1 = threading.Thread(target=escrever)
        t2 = threading.Thread(target=ler)
        
        t1.start()
        t2.start()
        
        t1.join()
        t2.join()
        
        # Assert
        assert len(leituras_realizadas) == 10
        # Todas as leituras devem ter sido bem-sucedidas (não erro)
        assert all("error" not in r for r in leituras_realizadas)


class TestConsultaRepositoryIntegracao:
    """Testes de integração do fluxo completo."""
    
    def test_fluxo_completo_consulta(self):
        """Testa o fluxo completo de uma consulta do início ao fim."""
        # Arrange
        repo = ConsultaRepository()
        id_consulta = "integracao_001"
        
        # Act & Assert em cada etapa
        # 1. Iniciar
        repo.iniciar_consulta(id_consulta, (2022, 2023), 1, 12)
        consulta = repo.obter_consulta(id_consulta)
        assert consulta["status"] == "processando"
        
        # 2. Adicionar dados do primeiro ano
        dados_2022 = [{"ano": 2022, "valor": "1.000,00"}]
        repo.adicionar_resultados_ano(id_consulta, 2022, dados_2022, 1, 12)
        consulta = repo.obter_consulta(id_consulta)
        assert 2022 in consulta["anos_concluidos"]
        assert 2023 in consulta["anos_pendentes"]
        
        # 3. Adicionar metadados
        repo.adicionar_metadados_ano(id_consulta, 2022, {"fonte": "local"})
        
        # 4. Adicionar dados do segundo ano
        dados_2023 = [{"ano": 2023, "valor": "2.000,00"}]
        repo.adicionar_resultados_ano(id_consulta, 2023, dados_2023, 1, 12)
        
        # 5. Finalizar
        repo.finalizar_consulta(id_consulta, status="concluido")
        consulta = repo.obter_consulta(id_consulta)
        
        # Assert final
        assert consulta["status"] == "concluido"
        assert consulta["total_registros"] == 2
        assert len(consulta["anos_processados"]) == 2
        
        # PRINCIPAL: Dados DEVEM estar no retorno final para evitar race condition
        assert "dados_por_ano" in consulta
        assert "2022" in consulta["dados_por_ano"]
        assert "2023" in consulta["dados_por_ano"]
        assert consulta["dados_ja_enviados"] is False