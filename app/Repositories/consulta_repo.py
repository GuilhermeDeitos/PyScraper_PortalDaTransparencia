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
    
    def iniciar_consulta(self, id_consulta: str, anos_range: Tuple[int, int]):
        """Inicia o registro de uma nova consulta"""
        ano_inicio, ano_fim = anos_range
        anos_pendentes = set(range(ano_inicio, ano_fim + 1))
        
        with self.lock:
            self.consultas[id_consulta] = {
                "status": "processando",
                "mensagem": f"Iniciando consulta para anos {ano_inicio} a {ano_fim}",
                "dados_por_ano": {},  # NOVO: Dados organizados por ano
                "anos_pendentes": anos_pendentes,
                "anos_concluidos": set(),
                "total_registros": 0
            }
    
    def adicionar_resultados_ano(self, id_consulta: str, ano: int, resultados: List[Dict[str, Any]]):
        """Adiciona os resultados de um ano à consulta"""
        with self.lock:
            if id_consulta in self.consultas:
                consulta = self.consultas[id_consulta]
                
                # Adiciona os resultados organizados por ano
                if resultados:
                    consulta["dados_por_ano"][ano] = {
                        "dados": resultados,
                        "total_registros": len(resultados),
                        "processado_em": str(datetime.datetime.now())
                    }
                    consulta["total_registros"] += len(resultados)
                else:
                    consulta["dados_por_ano"][ano] = {
                        "dados": [],
                        "total_registros": 0,
                        "processado_em": str(datetime.datetime.now())
                    }                
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
    
    def registrar_erro_ano(self, id_consulta: str, ano: int, erro: str):
        """Registra erro em um ano específico"""
        with self.lock:
            if id_consulta in self.consultas:
                consulta = self.consultas[id_consulta]
                consulta["mensagem"] += f" Erro no ano {ano}: {erro}"
                
                # Move o ano de pendente para concluído mesmo com erro
                if ano in consulta["anos_pendentes"]:
                    consulta["anos_pendentes"].remove(ano)
                    consulta["anos_concluidos"].add(ano)
    
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
        
        # Formata a saída de acordo com o status
        if consulta.get("status") == "concluido":
            return {
                "status": "concluido",
                "dados_por_ano": consulta.get("dados_por_ano", {}),
                "total_registros": consulta.get("total_registros", 0),
                "anos_processados": sorted(list(consulta.get("anos_concluidos", set()))),
                "resumo_por_ano": self._gerar_resumo_por_ano(consulta.get("dados_por_ano", {}))
            }
        elif consulta.get("status") == "erro":
            return {
                "status": "erro",
                "mensagem": consulta.get("mensagem", "Erro desconhecido na consulta"),
                "dados_parciais": consulta.get("dados_por_ano", {}) if consulta.get("dados_por_ano") else None
            }
        else:
            # Status processando - retorna dados parciais disponíveis
            return {
                "status": "processando",
                "mensagem": consulta.get("mensagem", "A consulta ainda está em processamento"),
                "anos_concluidos": sorted(list(consulta.get("anos_concluidos", set()))),
                "anos_pendentes": sorted(list(consulta.get("anos_pendentes", set()))),
                "dados_parciais": consulta.get("dados_por_ano", {}),
                "total_registros_ate_agora": consulta.get("total_registros", 0),
                "resumo_por_ano": self._gerar_resumo_por_ano(consulta.get("dados_por_ano", {}))
            }
    
    def _gerar_resumo_por_ano(self, dados_por_ano: Dict) -> Dict[int, Dict[str, Any]]:
        """Gera um resumo dos dados por ano"""
        resumo = {}
        for ano, info in dados_por_ano.items():
            resumo[ano] = {
                "total_registros": info.get("total_registros", 0),
                "processado_em": info.get("processado_em"),
                "tem_dados": len(info.get("dados", [])) > 0
            }
        return resumo