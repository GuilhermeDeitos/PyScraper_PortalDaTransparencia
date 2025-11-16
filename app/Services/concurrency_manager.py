import logging
import threading
import weakref
from concurrent.futures import ThreadPoolExecutor
from threading import Semaphore, Lock
from typing import Optional, Callable, Any
from dataclasses import dataclass

logger = logging.getLogger(__name__)

@dataclass
class ConcurrencyConfig:
    max_concurrent_scrapers: int = 8
    thread_name_prefix: str = "ScraperThread"

class ConcurrencyManager:
    """Gerencia controle de concorrência para scrapers."""
    
    def __init__(self, config: Optional[ConcurrencyConfig] = None):
        self.config = config or ConcurrencyConfig()
        self.semaphore = Semaphore(self.config.max_concurrent_scrapers)
        self.executor = ThreadPoolExecutor(
            max_workers=self.config.max_concurrent_scrapers,
            thread_name_prefix=self.config.thread_name_prefix
        )
        self.ano_locks = weakref.WeakValueDictionary()
        self.ano_locks_creation_lock = Lock()
    
    def get_lock_for_ano(self, ano: int) -> Lock:
        """Obtém ou cria um lock para um ano específico."""
        with self.ano_locks_creation_lock:
            lock = self.ano_locks.get(ano)
            if lock is None:
                lock = Lock()
                self.ano_locks[ano] = lock
            return lock
    
    def acquire_semaphore(self, blocking: bool = True, timeout: Optional[float] = None) -> bool:
        """Adquire o semáforo global."""
        return self.semaphore.acquire(blocking=blocking, timeout=timeout)
    
    def release_semaphore(self):
        """Libera o semáforo global."""
        self.semaphore.release()
    
    def submit_task(self, func: Callable, *args, **kwargs):
        """Submete uma tarefa ao pool de threads."""
        return self.executor.submit(func, *args, **kwargs)
    
    def get_available_slots(self) -> int:
        """Retorna número de slots disponíveis."""
        return self.semaphore._value
    
    def get_status(self) -> dict:
        """Retorna status do gerenciador de concorrência."""
        return {
            "max_workers": self.config.max_concurrent_scrapers,
            "available_slots": self.get_available_slots(),
            "active_threads": threading.active_count(),
            "executor_threads": len(self.executor._threads) if hasattr(self.executor, '_threads') else 0
        }
    
    def shutdown(self, wait: bool = True):
        """Encerra o executor de threads."""
        self.executor.shutdown(wait=wait)