import logging
from typing import List, Dict, Any

logger = logging.getLogger(__name__)

class DataValidator:
    """Valida integridade dos dados extraídos."""
    
    TAXA_VALIDADE_MINIMA = 0.8
    
    def validar_dados_ano(
        self, 
        dados: List[Dict[str, Any]], 
        ano: int
    ) -> List[Dict[str, Any]]:
        """Valida e filtra dados de um ano específico."""
        if not dados:
            return []
        
        dados_validos = []
        registros_invalidos = 0
        
        for registro in dados:
            if self._validar_registro(registro):
                registro['_ano_validado'] = ano
                dados_validos.append(registro)
            else:
                registros_invalidos += 1
        
        if registros_invalidos > 0:
            taxa_invalidos = registros_invalidos / len(dados)
            logger.warning(
                f"Ano {ano}: {registros_invalidos}/{len(dados)} registros inválidos ({taxa_invalidos:.1%})"
            )
        
        return dados_validos
    
    def _validar_registro(self, registro: Dict[str, Any]) -> bool:
        """Valida um registro individual."""
        if not self._validar_grupo_natureza_despesa(registro):
            return False
        
        if not self._validar_origem_recursos(registro):
            return False
        
        return True
    
    def _validar_grupo_natureza_despesa(self, registro: Dict[str, Any]) -> bool:
        """Valida campo GRUPO_NATUREZA_DESPESA."""
        if "GRUPO_NATUREZA_DESPESA" not in registro:
            return True
        
        valor = registro["GRUPO_NATUREZA_DESPESA"]
        if isinstance(valor, str) and (valor.startswith("O -") or valor.startswith("T -")):
            logger.debug(f"Campo GRUPO_NATUREZA_DESPESA com valor suspeito: {valor}")
            return False
        
        return True
    
    def _validar_origem_recursos(self, registro: Dict[str, Any]) -> bool:
        """Valida campo ORIGEM_RECURSOS."""
        if "ORIGEM_RECURSOS" not in registro:
            return True
        
        valor = str(registro["ORIGEM_RECURSOS"])
        if valor.replace(".", "").replace(",", "").isdigit() and len(valor) > 4:
            logger.debug(f"Campo ORIGEM_RECURSOS com valor numérico suspeito: {valor}")
            return False
        
        return True
    
    def validar_taxa_sucesso(
        self, 
        dados_validos: List[Dict[str, Any]], 
        dados_totais: List[Dict[str, Any]]
    ) -> bool:
        """Verifica se a taxa de validade está acima do mínimo aceitável."""
        if not dados_totais:
            return False
        
        taxa = len(dados_validos) / len(dados_totais)
        return taxa >= self.TAXA_VALIDADE_MINIMA