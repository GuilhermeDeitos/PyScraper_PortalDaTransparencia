import threading
import asyncio
import logging
from typing import Dict, Any, List, Set, Tuple, Optional
from datetime import datetime

logger = logging.getLogger(__name__)

class ConsultaPlaywrightRepository:
    """Repositório para gerenciar o estado das consultas Playwright em andamento"""
    
    def __init__(self):
        self.consultas = {}
        self.lock = threading.Lock()
    
    def iniciar_consulta(self, id_consulta: str, anos_range: Tuple[int, int]):
        """Inicia o registro de uma nova consulta Playwright"""
        ano_inicio, ano_fim = anos_range
        anos_pendentes = set(range(ano_inicio, ano_fim + 1))
        
        with self.lock:
            self.consultas[id_consulta] = {
                "status": "processando",
                "mensagem": f"Iniciando consulta Playwright para anos {ano_inicio} a {ano_fim}",
                "dados": [],
                "anos_pendentes": anos_pendentes,
                "anos_concluidos": set(),
                "anos_com_erro": set(),
                "total_registros": 0,
                "tipo_scraper": "playwright",
                "inicio": datetime.now(),
                "metricas": {
                    "tempo_total": 0,
                    "tempo_por_ano": {},
                    "registros_por_ano": {},
                    "erros_por_ano": {}
                }
            }
    
    def atualizar_status_processando(self, id_consulta: str, mensagem: str):
        """Atualiza o status de uma consulta em processamento"""
        with self.lock:
            if id_consulta in self.consultas:
                self.consultas[id_consulta]["mensagem"] = mensagem
                logger.info(f"[{id_consulta}] Status atualizado: {mensagem}")
    
    def adicionar_resultados_ano(self, id_consulta: str, ano: int, resultados: List[Dict[str, Any]], tempo_execucao: float = 0):
        """Adiciona os resultados de um ano à consulta Playwright"""
        with self.lock:
            if id_consulta in self.consultas:
                consulta = self.consultas[id_consulta]
                
                # Adiciona os resultados
                num_registros = 0
                if resultados:
                    consulta["dados"].extend(resultados)
                    num_registros = len(resultados)
                    consulta["total_registros"] += num_registros
                
                # Atualiza status do ano
                if ano in consulta["anos_pendentes"]:
                    consulta["anos_pendentes"].remove(ano)
                    consulta["anos_concluidos"].add(ano)
                
                # Atualiza métricas
                consulta["metricas"]["tempo_por_ano"][ano] = tempo_execucao
                consulta["metricas"]["registros_por_ano"][ano] = num_registros
                
                # Atualiza mensagem de progresso
                total_anos = len(consulta["anos_concluidos"]) + len(consulta["anos_pendentes"]) + len(consulta["anos_com_erro"])
                concluidos = len(consulta["anos_concluidos"])
                
                consulta["mensagem"] = f"Playwright: Processados {concluidos}/{total_anos} anos. Total: {consulta['total_registros']} registros"
                
                logger.info(f"[{id_consulta}] Ano {ano} processado - {num_registros} registros em {tempo_execucao:.2f}s")
    
    def adicionar_erro_ano(self, id_consulta: str, ano: int, erro: str):
        """Registra um erro para um ano específico"""
        with self.lock:
            if id_consulta in self.consultas:
                consulta = self.consultas[id_consulta]
                
                # Remove dos pendentes e adiciona aos com erro
                if ano in consulta["anos_pendentes"]:
                    consulta["anos_pendentes"].remove(ano)
                    consulta["anos_com_erro"].add(ano)
                
                # Registra o erro nas métricas
                consulta["metricas"]["erros_por_ano"][ano] = erro
                
                # Atualiza mensagem
                total_anos = len(consulta["anos_concluidos"]) + len(consulta["anos_pendentes"]) + len(consulta["anos_com_erro"])
                concluidos = len(consulta["anos_concluidos"])
                com_erro = len(consulta["anos_com_erro"])
                
                consulta["mensagem"] = f"Playwright: {concluidos}/{total_anos} anos OK, {com_erro} com erro. Total: {consulta['total_registros']} registros"
                
                logger.error(f"[{id_consulta}] Erro no ano {ano}: {erro}")
    
    def finalizar_consulta_sucesso(self, id_consulta: str):
        """Marca uma consulta como concluída com sucesso"""
        with self.lock:
            if id_consulta in self.consultas:
                consulta = self.consultas[id_consulta]
                consulta["status"] = "concluido"
                
                # Calcula tempo total
                tempo_total = (datetime.now() - consulta["inicio"]).total_seconds()
                consulta["metricas"]["tempo_total"] = tempo_total
                
                total_anos = len(consulta["anos_concluidos"]) + len(consulta["anos_com_erro"])
                anos_ok = len(consulta["anos_concluidos"])
                anos_erro = len(consulta["anos_com_erro"])
                
                consulta["mensagem"] = (f"Playwright: Consulta concluída! {anos_ok}/{total_anos} anos processados, "
                                      f"{consulta['total_registros']} registros em {tempo_total:.2f}s")
                
                if anos_erro > 0:
                    consulta["mensagem"] += f" ({anos_erro} anos com erro)"
                
                logger.info(f"[{id_consulta}] Consulta Playwright finalizada: {consulta['mensagem']}")
    
    def finalizar_consulta_erro(self, id_consulta: str, erro: str):
        """Marca uma consulta como finalizada com erro"""
        with self.lock:
            if id_consulta in self.consultas:
                consulta = self.consultas[id_consulta]
                consulta["status"] = "erro"
                
                # Calcula tempo total
                tempo_total = (datetime.now() - consulta["inicio"]).total_seconds()
                consulta["metricas"]["tempo_total"] = tempo_total
                
                consulta["mensagem"] = f"Playwright: Erro na consulta: {erro}"
                consulta["erro"] = erro
                
                logger.error(f"[{id_consulta}] Consulta Playwright finalizada com erro: {erro}")
    
    def obter_consulta(self, id_consulta: str) -> Optional[Dict[str, Any]]:
        """Obtém os dados de uma consulta"""
        with self.lock:
            if id_consulta in self.consultas:
                return self.consultas[id_consulta].copy()
            return None
    
    def consulta_existe(self, id_consulta: str) -> bool:
        """Verifica se uma consulta existe"""
        with self.lock:
            return id_consulta in self.consultas
    
    def listar_consultas_ativas(self) -> List[str]:
        """Lista todas as consultas em processamento"""
        with self.lock:
            return [id_consulta for id_consulta, dados in self.consultas.items() 
                   if dados["status"] == "processando"]
    
    def obter_estatisticas_consulta(self, id_consulta: str) -> Optional[Dict[str, Any]]:
        """Obtém estatísticas detalhadas de uma consulta"""
        consulta = self.obter_consulta(id_consulta)
        if not consulta:
            return None
        
        estatisticas = {
            "id_consulta": id_consulta,
            "tipo_scraper": "playwright",
            "status": consulta["status"],
            "total_registros": consulta["total_registros"],
            "anos_concluidos": len(consulta["anos_concluidos"]),
            "anos_pendentes": len(consulta["anos_pendentes"]),
            "anos_com_erro": len(consulta["anos_com_erro"]),
            "tempo_total": consulta["metricas"]["tempo_total"],
            "metricas_detalhadas": consulta["metricas"]
        }
        
        if consulta["metricas"]["tempo_por_ano"]:
            tempos = list(consulta["metricas"]["tempo_por_ano"].values())
            estatisticas["tempo_medio_por_ano"] = sum(tempos) / len(tempos)
            estatisticas["tempo_min_ano"] = min(tempos)
            estatisticas["tempo_max_ano"] = max(tempos)
        
        if consulta["metricas"]["registros_por_ano"]:
            registros = list(consulta["metricas"]["registros_por_ano"].values())
            estatisticas["registros_medio_por_ano"] = sum(registros) / len(registros)
            estatisticas["registros_min_ano"] = min(registros)
            estatisticas["registros_max_ano"] = max(registros)
        
        return estatisticas
    
    def limpar_consultas_antigas(self, horas: int = 24):
        """Remove consultas mais antigas que o número de horas especificado"""
        with self.lock:
            agora = datetime.now()
            ids_para_remover = []
            
            for id_consulta, dados in self.consultas.items():
                idade = (agora - dados["inicio"]).total_seconds() / 3600  # em horas
                if idade > horas and dados["status"] in ["concluido", "erro"]:
                    ids_para_remover.append(id_consulta)
            
            for id_consulta in ids_para_remover:
                del self.consultas[id_consulta]
                logger.info(f"Consulta antiga removida: {id_consulta}")
            
            return len(ids_para_remover)
