import datetime
import threading
import logging
import time
from typing import Dict, Any, List, Set, Tuple

logger = logging.getLogger(__name__)

class ConsultaRepository:
    """Repositório para gerenciar o estado das consultas em andamento organizadas por ano"""
    
    def __init__(self):
        self.consultas = {}
        self.lock = threading.Lock()
    
    def iniciar_consulta(self, id_consulta: str, anos_range: Tuple[int, int], mes_inicio: int = None, mes_fim: int = None):
        """Inicia o registro de uma nova consulta organizando por anos"""
        ano_inicio, ano_fim = anos_range
        anos_pendentes = set(range(ano_inicio, ano_fim + 1))
        
        with self.lock:
            self.consultas[id_consulta] = {
                "status": "processando",
                "mensagem": f"Iniciando consulta para anos {ano_inicio} a {ano_fim}",
                "dados_por_ano": {},  # Dados organizados por ano
                "anos_pendentes": anos_pendentes,
                "anos_concluidos": set(),
                "total_registros": 0,
                "mes_inicio": mes_inicio,
                "mes_fim": mes_fim,
                "iniciado_em": str(datetime.datetime.now()),
                "resumo_por_ano": {}
            }
    
    def adicionar_resultados_ano(self, id_consulta: str, ano: int, resultados: List[Dict[str, Any]], 
                                mes_inicio: int = None, mes_fim: int = None):
        """Adiciona os resultados de um ano à consulta"""
        with self.lock:
            if id_consulta in self.consultas:
                consulta = self.consultas[id_consulta]
                
                # Adiciona os resultados organizados por ano
                if resultados:
                    consulta["dados_por_ano"][str(ano)] = {
                        "dados": resultados,
                        "total_registros": len(resultados),
                        "mes_inicio": mes_inicio,
                        "mes_fim": mes_fim,
                        "processado_em": str(datetime.datetime.now())
                    }
                    consulta["total_registros"] += len(resultados)
                    
                    # Gera resumo do ano
                    consulta["resumo_por_ano"][str(ano)] = self._gerar_resumo_ano(resultados)
                else:
                    consulta["dados_por_ano"][str(ano)] = {
                        "dados": [],
                        "total_registros": 0,
                        "mes_inicio": mes_inicio,
                        "mes_fim": mes_fim,
                        "processado_em": str(datetime.datetime.now())
                    }
                    consulta["resumo_por_ano"][str(ano)] = {"total_registros": 0, "sem_dados": True}
                
                # Atualiza status do ano
                if ano in consulta["anos_pendentes"]:
                    consulta["anos_pendentes"].remove(ano)
                    consulta["anos_concluidos"].add(ano)
                
                # Atualiza mensagem
                total_anos = len(consulta["anos_concluidos"]) + len(consulta["anos_pendentes"])
                consulta["mensagem"] = (
                    f"Processados {len(consulta['anos_concluidos'])} de {total_anos} anos. "
                    f"Total: {consulta['total_registros']} registros."
                )
                
                logger.info(f"Ano {ano} concluído: {len(resultados)} registros")
    
    def atualizar_status_processando(self, id_consulta: str, mensagem: str):
        """Atualiza o status de uma consulta em processamento"""
        with self.lock:
            if id_consulta in self.consultas:
                self.consultas[id_consulta]["mensagem"] = mensagem
                self.consultas[id_consulta]["ultima_atualizacao"] = str(datetime.datetime.now())
    
    def registrar_erro_ano(self, id_consulta: str, ano: int, erro: str):
        """Registra erro em um ano específico"""
        with self.lock:
            if id_consulta in self.consultas:
                consulta = self.consultas[id_consulta]
                
                # Adiciona informação do erro ao ano
                if "erros_por_ano" not in consulta:
                    consulta["erros_por_ano"] = {}
                consulta["erros_por_ano"][str(ano)] = {
                    "erro": erro,
                    "ocorrido_em": str(datetime.datetime.now())
                }
                
                consulta["mensagem"] += f" Erro no ano {ano}: {erro}"
                
                # Move o ano de pendente para concluído mesmo com erro
                if ano in consulta["anos_pendentes"]:
                    consulta["anos_pendentes"].remove(ano)
                    consulta["anos_concluidos"].add(ano)
                
                # Marca o ano como processado mas com erro
                consulta["dados_por_ano"][str(ano)] = {
                    "dados": [],
                    "total_registros": 0,
                    "erro": erro,
                    "processado_em": str(datetime.datetime.now())
                }
    
    # Ajuste o método finalizar_consulta para garantir que o status esteja na raiz do objeto:
    def finalizar_consulta(self, id_consulta: str, status: str = "concluido"):
        """Marca uma consulta como concluída"""
        with self.lock:
            # Recuperar consulta atual
            consulta = self.consultas.get(id_consulta)
            if not consulta:
                logger.warning(f"Consulta {id_consulta} não encontrada para finalização")
                return
            
            # Verificar se TODOS os anos foram realmente processados
            anos_concluidos = consulta.get("anos_concluidos", set())
            anos_pendentes = consulta.get("anos_pendentes", set())
            
            if anos_pendentes:
                logger.warning(
                    f"Consulta {id_consulta} tem {len(anos_pendentes)} anos pendentes: {anos_pendentes}. "
                    "Não finalizando ainda."
                )
                # NÃO finalizar se ainda há anos pendentes
                return
            
            # Verificar se dados_por_ano contém TODOS os anos esperados
            dados_por_ano = consulta.get("dados_por_ano", {})
            total_anos_esperados = len(anos_concluidos)
            total_anos_com_dados = len(dados_por_ano)
            
            if total_anos_com_dados < total_anos_esperados:
                logger.warning(
                    f"Consulta {id_consulta}: Esperados {total_anos_esperados} anos, "
                    f"mas apenas {total_anos_com_dados} têm dados. Aguardando..."
                )
                return
            
            # Atualizar status
            consulta["status"] = status
            consulta["concluido_em"] = time.strftime("%Y-%m-%d %H:%M:%S")
            
            # Gerar resumos
            if status == "concluido":
                try:
                    logger.info(
                        f"Consulta {id_consulta} concluída com sucesso. "
                        f"Total de {len(anos_concluidos)} anos processados"
                    )
                    consulta["resumo"] = self._gerar_resumo_consolidado(consulta)
                except Exception as e:
                    logger.error(f"Erro ao gerar resumo para consulta {id_consulta}: {e}")
    
    def registrar_erro_consulta(self, id_consulta: str, erro: str):
        """Registra erro na consulta inteira"""
        with self.lock:
            if id_consulta in self.consultas:
                self.consultas[id_consulta]["status"] = "erro"
                self.consultas[id_consulta]["erro_geral"] = erro
                self.consultas[id_consulta]["erro_em"] = str(datetime.datetime.now())
                self.consultas[id_consulta]["mensagem"] = f"Erro: {erro}"
    
    def obter_consulta(self, id_consulta: str) -> Dict[str, Any]:
        """Obtém os dados de uma consulta pelo ID com dados organizados por ano"""
        with self.lock:
            if id_consulta not in self.consultas:
                return {"error": "Consulta não encontrada"}
            
            consulta = dict(self.consultas[id_consulta])
        
        # Formata a saída de acordo com o status
        if consulta.get("status") == "concluido":
            return {
                "status": "concluido",
                "total_registros": consulta.get("total_registros", 0),
                "anos_processados": sorted(list(consulta.get("anos_concluidos", set()))),
                "erros_por_ano": consulta.get("erros_por_ano", {}),
                "iniciado_em": consulta.get("iniciado_em"),
                "finalizado_em": consulta.get("finalizado_em"),
                "periodo_consulta": {
                    "mes_inicio": consulta.get("mes_inicio"),
                    "mes_fim": consulta.get("mes_fim")
                },
                "dados_ja_enviados": True
            }
        elif consulta.get("status") == "erro":
            return {
                "status": "erro",
                "mensagem": consulta.get("mensagem", "Erro desconhecido na consulta"),
                "erro_geral": consulta.get("erro_geral"),
                "erro_em": consulta.get("erro_em"),
                "dados_parciais": consulta.get("dados_por_ano", {}) if consulta.get("dados_por_ano") else None,
                "erros_por_ano": consulta.get("erros_por_ano", {})
            }
        else:
            # Status processando - retorna dados parciais disponíveis por ano
            return {
                "status": "processando",
                "mensagem": consulta.get("mensagem", "A consulta ainda está em processamento"),
                "anos_concluidos": sorted(list(consulta.get("anos_concluidos", set()))),
                "anos_pendentes": sorted(list(consulta.get("anos_pendentes", set()))),
                "dados_parciais_por_ano": consulta.get("dados_por_ano", {}),
                "total_registros_ate_agora": consulta.get("total_registros", 0),
                "ultima_atualizacao": consulta.get("ultima_atualizacao"),
                "erros_por_ano": consulta.get("erros_por_ano", {}),
                "periodo_consulta": {
                    "mes_inicio": consulta.get("mes_inicio"),
                    "mes_fim": consulta.get("mes_fim")
                }
            }
    
    def _gerar_resumo_ano(self, dados_ano: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Gera um resumo estatístico dos dados de um ano"""
        if not dados_ano:
            return {"total_registros": 0, "sem_dados": True}
        
        # Campos monetários para análise
        campos_monetarios = [
            'ORÇAMENTO_INICIAL___LOA_(R$)',
            'TOTAL_ORÇAMENTÁRIO_(R$)_ATE_MES', 
            'EMPENHADO_(R$)_ATE_MES',
            'LIQUIDADO_(R$)_ATE_MES',
            'PAGO_(R$)_ATE_MES'
        ]
        
        resumo = {
            "total_registros": len(dados_ano),
            "valores_totais": {},
            "unidades_orcamentarias": set(),
            "funcoes": set(),
            "origens_recursos": set()
        }
        
        # Calcular totais por campo monetário
        for campo in campos_monetarios:
            total = 0
            for registro in dados_ano:
                valor_str = registro.get(campo, "0,00")
                if valor_str and valor_str != "0,00":
                    # Converter string brasileira para float
                    valor = self._converter_valor_brasileiro_para_float(valor_str)
                    total += valor
            resumo["valores_totais"][campo] = total
        
        # Coletar informações únicas
        for registro in dados_ano:
            if registro.get("UNIDADE_ORÇAMENTÁRIA"):
                resumo["unidades_orcamentarias"].add(registro["UNIDADE_ORÇAMENTÁRIA"])
            if registro.get("FUNÇÃO"):
                resumo["funcoes"].add(registro["FUNÇÃO"])
            if registro.get("ORIGEM_DOS_RECURSOS"):
                resumo["origens_recursos"].add(registro["ORIGEM_DOS_RECURSOS"])
        
        # Converter sets para listas para JSON
        resumo["unidades_orcamentarias"] = list(resumo["unidades_orcamentarias"])
        resumo["funcoes"] = list(resumo["funcoes"])
        resumo["origens_recursos"] = list(resumo["origens_recursos"])
        
        return resumo
    
    def _gerar_resumo_consolidado(self, consulta: Dict[str, Any]) -> Dict[str, Any]:
        """Gera resumo consolidado de todos os anos processados"""
        dados_por_ano = consulta.get("dados_por_ano", {})
        
        consolidado = {
            "total_registros": consulta.get("total_registros", 0),
            "anos_processados": sorted([int(ano) for ano in dados_por_ano.keys()]),
            "distribuicao_por_ano": {},
            "valores_consolidados": {},
            "periodo_total": {
                "mes_inicio": consulta.get("mes_inicio"),
                "mes_fim": consulta.get("mes_fim"),
                "anos_abrangidos": len(dados_por_ano)
            }
        }
        
        # Campos monetários para consolidação
        campos_monetarios = [
            'ORÇAMENTO_INICIAL___LOA_(R$)',
            'TOTAL_ORÇAMENTÁRIO_(R$)_ATE_MES',
            'EMPENHADO_(R$)_ATE_MES',
            'LIQUIDADO_(R$)_ATE_MES',
            'PAGO_(R$)_ATE_MES'
        ]
        
        # Calcular valores consolidados
        for campo in campos_monetarios:
            total_campo = 0
            for ano, dados_ano in dados_por_ano.items():
                total_ano = 0
                for registro in dados_ano.get("dados", []):
                    valor_str = registro.get(campo, "0,00")
                    if valor_str and valor_str != "0,00":
                        valor = self._converter_valor_brasileiro_para_float(valor_str)
                        total_ano += valor
                total_campo += total_ano
                
                # Guardar distribuição por ano
                if ano not in consolidado["distribuicao_por_ano"]:
                    consolidado["distribuicao_por_ano"][ano] = {}
                consolidado["distribuicao_por_ano"][ano][campo] = total_ano
            
            consolidado["valores_consolidados"][campo] = total_campo
        
        return consolidado
    
    def _converter_valor_brasileiro_para_float(self, valor_str: str) -> float:
        """Converte string no formato brasileiro para float"""
        if not valor_str or valor_str in ["", "0,00", "-"]:
            return 0.0
        
        try:
            # Remove espaços e pontos (separadores de milhares)
            valor_limpo = valor_str.replace(".", "").replace(" ", "")
            # Substitui vírgula por ponto (separador decimal)
            valor_limpo = valor_limpo.replace(",", ".")
            return float(valor_limpo)
        except:
            return 0.0
    def adicionar_metadados_ano(self, id_consulta: str, ano: int, metadados: dict):
        """
        Adiciona metadados para um ano específico da consulta.
        
        Args:
            id_consulta: ID único da consulta
            ano: Ano para adicionar metadados
            metadados: Dicionário com metadados a serem armazenados
        """
        consulta = self.consultas.get(id_consulta)
        if not consulta:
            return
        
        if "metadados_anos" not in consulta:
            consulta["metadados_anos"] = {}
        
        if str(ano) not in consulta["metadados_anos"]:
            consulta["metadados_anos"][str(ano)] = {}
        
        # Adiciona os novos metadados ao dicionário existente
        consulta["metadados_anos"][str(ano)].update(metadados)