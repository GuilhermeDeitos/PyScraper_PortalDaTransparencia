import datetime
import threading
import logging
from typing import Dict, Any, List, Set, Tuple

logger = logging.getLogger(__name__)

class ConsultaRepository:
    """Repositório para gerenciar o estado das consultas em andamento"""
    
    def __init__(self):
        self.consultas = {}
        self.lock = threading.Lock()
    
    def iniciar_consulta(self, id_consulta: str, anos_range: Tuple[int, int], mes_inicio: int, mes_fim: int):
        """Inicia o registro de uma nova consulta"""
        ano_inicio, ano_fim = anos_range
        
        # Gera todos os períodos mês/ano que serão processados
        periodos_pendentes = self._gerar_periodos_consulta(ano_inicio, ano_fim, mes_inicio, mes_fim)
        
        with self.lock:
            self.consultas[id_consulta] = {
                "status": "processando",
                "mensagem": f"Iniciando consulta de {mes_inicio:02d}/{ano_inicio} a {mes_fim:02d}/{ano_fim}",
                "dados_por_periodo": {},  # Dados organizados por período (ano-mes)
                "periodos_pendentes": periodos_pendentes,
                "periodos_concluidos": set(),
                "total_registros": 0,
                "meta_consulta": {
                    "ano_inicio": ano_inicio,
                    "ano_fim": ano_fim,
                    "mes_inicio": mes_inicio,
                    "mes_fim": mes_fim
                }
            }
    
    def _gerar_periodos_consulta(self, ano_inicio: int, ano_fim: int, mes_inicio: int, mes_fim: int) -> Set[str]:
        """Gera todos os períodos mês/ano que serão consultados"""
        periodos = set()
                
        if ano_inicio == ano_fim:
            # Mesmo ano: apenas os meses especificados
            for mes in range(mes_inicio, mes_fim + 1):
                periodo = f"{ano_inicio}-{mes:02d}"
                periodos.add(periodo)
        else:
            # Múltiplos anos
            # Primeiro ano: do mês inicial até dezembro
            for mes in range(mes_inicio, 13):
                periodo = f"{ano_inicio}-{mes:02d}"
                periodos.add(periodo)
            
            # Anos intermediários: todos os meses
            for ano in range(ano_inicio + 1, ano_fim):
                for mes in range(1, 13):
                    periodo = f"{ano}-{mes:02d}"
                    periodos.add(periodo)
            
            # Último ano: de janeiro até o mês final
            for mes in range(1, mes_fim + 1):
                periodo = f"{ano_fim}-{mes:02d}"
                periodos.add(periodo)
        
        return periodos
    
    def adicionar_resultados_periodo(self, id_consulta: str, ano: int, mes: int, resultados: List[Dict[str, Any]]):
        """Adiciona os resultados de um período específico à consulta"""
        periodo = f"{ano}-{mes:02d}"
        
        with self.lock:
            if id_consulta in self.consultas:
                consulta = self.consultas[id_consulta]
                
                # Adiciona os resultados organizados por período
                if resultados:
                    consulta["dados_por_periodo"][periodo] = {
                        "dados": resultados,
                        "total_registros": len(resultados),
                        "ano": ano,
                        "mes": mes,
                        "processado_em": str(datetime.datetime.now())
                    }
                    consulta["total_registros"] += len(resultados)
                else:
                    consulta["dados_por_periodo"][periodo] = {
                        "dados": [],
                        "total_registros": 0,
                        "ano": ano,
                        "mes": mes,
                        "processado_em": str(datetime.datetime.now())
                    }
                
                # Atualiza status do período
                if periodo in consulta["periodos_pendentes"]:
                    consulta["periodos_pendentes"].remove(periodo)
                    consulta["periodos_concluidos"].add(periodo)
                
                # Atualiza mensagem
                total_periodos = len(consulta["periodos_concluidos"]) + len(consulta["periodos_pendentes"])
                consulta["mensagem"] = (
                    f"Processados {len(consulta['periodos_concluidos'])} de {total_periodos} períodos. "
                    f"Total: {consulta['total_registros']} registros."
                )
                
                logger.info(f"Período {periodo} concluído: {len(resultados)} registros")
    
    def adicionar_resultados_ano(self, id_consulta: str, ano: int, resultados: List[Dict[str, Any]]):
        """Adiciona os resultados de um ano à consulta (compatibilidade com código atual)"""
        with self.lock:
            if id_consulta in self.consultas:
                consulta = self.consultas[id_consulta]
                meta = consulta.get("meta_consulta", {})
                
                # Determina quais meses deste ano devem ser processados
                if ano == meta.get("ano_inicio") and ano == meta.get("ano_fim"):
                    # Mesmo ano: mês inicial ao final
                    mes_inicial_ano = meta.get("mes_inicio", 1)
                    mes_final_ano = meta.get("mes_fim", 12)
                elif ano == meta.get("ano_inicio"):
                    # Primeiro ano: mês inicial a dezembro
                    mes_inicial_ano = meta.get("mes_inicio", 1)
                    mes_final_ano = 12
                elif ano == meta.get("ano_fim"):
                    # Último ano: janeiro ao mês final
                    mes_inicial_ano = 1
                    mes_final_ano = meta.get("mes_fim", 12)
                else:
                    # Ano intermediário: todos os meses
                    mes_inicial_ano = 1
                    mes_final_ano = 12
                
                # Distribui os dados pelos meses (aproximação)
                total_meses = mes_final_ano - mes_inicial_ano + 1
                registros_por_mes = len(resultados) // total_meses if resultados else 0
                
                for mes in range(mes_inicial_ano, mes_final_ano + 1):
                    # Calcula quantos registros atribuir a este mês
                    if mes == mes_final_ano:
                        # Último mês recebe o restante
                        inicio_idx = (mes - mes_inicial_ano) * registros_por_mes
                        dados_mes = resultados[inicio_idx:] if resultados else []
                    else:
                        inicio_idx = (mes - mes_inicial_ano) * registros_por_mes
                        fim_idx = inicio_idx + registros_por_mes
                        dados_mes = resultados[inicio_idx:fim_idx] if resultados else []
                    
                    self.adicionar_resultados_periodo(id_consulta, ano, mes, dados_mes)
    
    def atualizar_status_processando(self, id_consulta: str, mensagem: str):
        """Atualiza o status de uma consulta em processamento"""
        with self.lock:
            if id_consulta in self.consultas:
                self.consultas[id_consulta]["mensagem"] = mensagem
    
    def registrar_erro_periodo(self, id_consulta: str, ano: int, mes: int, erro: str):
        """Registra erro em um período específico"""
        periodo = f"{ano}-{mes:02d}"
        
        with self.lock:
            if id_consulta in self.consultas:
                consulta = self.consultas[id_consulta]
                consulta["mensagem"] += f" Erro no período {periodo}: {erro}"
                
                # Move o período de pendente para concluído mesmo com erro
                if periodo in consulta["periodos_pendentes"]:
                    consulta["periodos_pendentes"].remove(periodo)
                    consulta["periodos_concluidos"].add(periodo)
    
    def registrar_erro_ano(self, id_consulta: str, ano: int, erro: str):
        """Registra erro em um ano específico (compatibilidade)"""
        with self.lock:
            if id_consulta in self.consultas:
                consulta = self.consultas[id_consulta]
                meta = consulta.get("meta_consulta", {})
                
                # Marca todos os períodos deste ano como com erro
                if ano == meta.get("ano_inicio") and ano == meta.get("ano_fim"):
                    mes_inicial = meta.get("mes_inicio", 1)
                    mes_final = meta.get("mes_fim", 12)
                elif ano == meta.get("ano_inicio"):
                    mes_inicial = meta.get("mes_inicio", 1)
                    mes_final = 12
                elif ano == meta.get("ano_fim"):
                    mes_inicial = 1
                    mes_final = meta.get("mes_fim", 12)
                else:
                    mes_inicial = 1
                    mes_final = 12
                
                for mes in range(mes_inicial, mes_final + 1):
                    self.registrar_erro_periodo(id_consulta, ano, mes, erro)
    
    def finalizar_consulta(self, id_consulta: str):
        """Marca uma consulta como concluída"""
        with self.lock:
            if id_consulta in self.consultas:
                consulta = self.consultas[id_consulta]
                consulta["status"] = "concluido"
                consulta["mensagem"] = f"Consulta concluída. Total: {consulta['total_registros']} registros."
                logger.info(f"Consulta {id_consulta} concluída com sucesso")
    
    def registrar_erro_consulta(self, id_consulta: str, erro: str):
        """Registra erro na consulta inteira"""
        with self.lock:
            if id_consulta in self.consultas:
                self.consultas[id_consulta]["status"] = "erro"
                self.consultas[id_consulta]["mensagem"] = f"Erro: {erro}"
    
    def obter_consulta(self, id_consulta: str) -> Dict[str, Any]:
        """Obtém os dados de uma consulta pelo ID com dados parciais"""
        with self.lock:
            if id_consulta not in self.consultas:
                return {"error": "Consulta não encontrada"}
            
            consulta = dict(self.consultas[id_consulta])
        
        # Organiza dados por ano para compatibilidade
        dados_por_ano = self._organizar_dados_por_ano(consulta.get("dados_por_periodo", {}))
        
        # Formata a saída de acordo com o status
        if consulta.get("status") == "concluido":
            return {
                "status": "concluido",
                "dados_por_ano": dados_por_ano,
                "dados_por_periodo": consulta.get("dados_por_periodo", {}),
                "total_registros": consulta.get("total_registros", 0),
                "periodos_processados": sorted(list(consulta.get("periodos_concluidos", set()))),
                "anos_processados": sorted(list(set(self._extrair_anos_de_periodos(consulta.get("periodos_concluidos", set()))))),
                "resumo_por_periodo": self._gerar_resumo_por_periodo(consulta.get("dados_por_periodo", {})),
                "resumo_por_ano": self._gerar_resumo_por_ano(dados_por_ano)
            }
        elif consulta.get("status") == "erro":
            return {
                "status": "erro",
                "mensagem": consulta.get("mensagem", "Erro desconhecido na consulta"),
                "dados_parciais_por_ano": dados_por_ano if dados_por_ano else None,
                "dados_parciais_por_periodo": consulta.get("dados_por_periodo", {}) if consulta.get("dados_por_periodo") else None
            }
        else:
            # Status processando - retorna dados parciais disponíveis
            return {
                "status": "processando",
                "mensagem": consulta.get("mensagem", "A consulta ainda está em processamento"),
                "periodos_concluidos": sorted(list(consulta.get("periodos_concluidos", set()))),
                "periodos_pendentes": sorted(list(consulta.get("periodos_pendentes", set()))),
                "anos_concluidos": sorted(list(set(self._extrair_anos_de_periodos(consulta.get("periodos_concluidos", set()))))),
                "anos_pendentes": sorted(list(set(self._extrair_anos_de_periodos(consulta.get("periodos_pendentes", set()))))),
                "dados_parciais_por_ano": dados_por_ano,
                "dados_parciais_por_periodo": consulta.get("dados_por_periodo", {}),
                "total_registros_ate_agora": consulta.get("total_registros", 0),
                "resumo_por_periodo": self._gerar_resumo_por_periodo(consulta.get("dados_por_periodo", {})),
                "resumo_por_ano": self._gerar_resumo_por_ano(dados_por_ano)
            }
    
    def _organizar_dados_por_ano(self, dados_por_periodo: Dict) -> Dict[int, Dict[str, Any]]:
        """Organiza os dados por período em dados por ano para compatibilidade"""
        dados_por_ano = {}
        
        for periodo, dados_periodo in dados_por_periodo.items():
            ano = dados_periodo["ano"]
            
            if ano not in dados_por_ano:
                dados_por_ano[ano] = {
                    "dados": [],
                    "total_registros": 0,
                    "periodos": [],
                    "processado_em": dados_periodo.get("processado_em")
                }
            
            dados_por_ano[ano]["dados"].extend(dados_periodo.get("dados", []))
            dados_por_ano[ano]["total_registros"] += dados_periodo.get("total_registros", 0)
            dados_por_ano[ano]["periodos"].append(periodo)
            
            # Atualiza data de processamento com a mais recente
            if dados_periodo.get("processado_em"):
                if not dados_por_ano[ano]["processado_em"] or dados_periodo["processado_em"] > dados_por_ano[ano]["processado_em"]:
                    dados_por_ano[ano]["processado_em"] = dados_periodo["processado_em"]
        
        return dados_por_ano
    
    def _extrair_anos_de_periodos(self, periodos: Set[str]) -> List[int]:
        """Extrai os anos únicos de uma lista de períodos"""
        anos = []
        for periodo in periodos:
            if "-" in periodo:
                ano = int(periodo.split("-")[0])
                anos.append(ano)
        return anos
    
    def _gerar_resumo_por_periodo(self, dados_por_periodo: Dict) -> Dict[str, Dict[str, Any]]:
        """Gera um resumo dos dados por período"""
        resumo = {}
        for periodo, info in dados_por_periodo.items():
            resumo[periodo] = {
                "ano": info.get("ano"),
                "mes": info.get("mes"),
                "total_registros": info.get("total_registros", 0),
                "processado_em": info.get("processado_em"),
                "tem_dados": len(info.get("dados", [])) > 0
            }
        return resumo
    
    def _gerar_resumo_por_ano(self, dados_por_ano: Dict) -> Dict[int, Dict[str, Any]]:
        """Gera um resumo dos dados por ano"""
        resumo = {}
        for ano, info in dados_por_ano.items():
            resumo[ano] = {
                "total_registros": info.get("total_registros", 0),
                "processado_em": info.get("processado_em"),
                "tem_dados": len(info.get("dados", [])) > 0,
                "periodos_processados": info.get("periodos", [])
            }
        return resumo