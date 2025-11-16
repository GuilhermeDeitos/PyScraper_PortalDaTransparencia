import pytest
from app.Services.concurrency_manager import ConcurrencyManager, ConcurrencyConfig

class TestConcurrencyManager:
    
    def test_inicializacao_padrao(self):
        manager = ConcurrencyManager()
        assert manager.config.max_concurrent_scrapers == 8
        assert manager.get_available_slots() == 8
    
    def test_inicializacao_customizada(self):
        config = ConcurrencyConfig(max_concurrent_scrapers=4)
        manager = ConcurrencyManager(config)
        assert manager.get_available_slots() == 4
    
    def test_get_lock_for_ano_cria_novo_lock(self):
        manager = ConcurrencyManager()
        lock1 = manager.get_lock_for_ano(2023)
        lock2 = manager.get_lock_for_ano(2023)
        assert lock1 is lock2
    
    def test_get_lock_for_ano_locks_diferentes(self):
        manager = ConcurrencyManager()
        lock_2023 = manager.get_lock_for_ano(2023)
        lock_2024 = manager.get_lock_for_ano(2024)
        assert lock_2023 is not lock_2024
    
    def test_acquire_release_semaphore(self):
        manager = ConcurrencyManager(ConcurrencyConfig(max_concurrent_scrapers=2))
        
        assert manager.get_available_slots() == 2
        
        manager.acquire_semaphore()
        assert manager.get_available_slots() == 1
        
        manager.release_semaphore()
        assert manager.get_available_slots() == 2
    
    def test_submit_task(self):
        manager = ConcurrencyManager()
        
        def tarefa_teste():
            return 42
        
        future = manager.submit_task(tarefa_teste)
        resultado = future.result(timeout=1)
        
        assert resultado == 42