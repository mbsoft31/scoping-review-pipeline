import pytest
import asyncio
from srp.async_queue.worker import Worker, WorkerPool
from srp.async_queue.task_queue import TaskQueue, SearchTask, TaskStatus
from srp.async_queue.error_handler import ErrorHandler, ErrorType, CircuitBreaker

def fake_search_success(*args, **kwargs):
    async def _run(**kw): return ["ok"]
    return _run

def fake_search_error(*args, **kwargs):
    async def _run(**kw): raise ValueError("mock fail")
    return _run

@pytest.mark.asyncio
async def test_worker_success(monkeypatch, tmp_path):
    queue = TaskQueue(persist_dir=tmp_path)
    task = SearchTask(source="dummy", query="success")
    tid = await queue.enqueue(task)
    # Monkeypatch orchestrator to always succeed
    class DummyOrchestrator:
        async def search_source(self, **kwargs):
            return ["ok"]
    from srp.async_queue.worker import SearchCache  # or a mock/cache as appropriate
    worker = Worker(0, queue, DummyOrchestrator(), SearchCache(tmp_path))
    await worker.run()  # Will exit after task is done
    assert queue.get_task(tid).status == TaskStatus.COMPLETED

@pytest.mark.asyncio
async def test_error_handler_and_circuit_breaker():
    eh = ErrorHandler()
    class DummyResp: status_code = 429
    class DummyErr(Exception): response = DummyResp()
    t = DummyErr()
    assert eh.classify_error(t) == ErrorType.RATE_LIMIT
    cb = CircuitBreaker(failure_threshold=2, recovery_timeout=1)
    for _ in range(3):
        try:
            await cb.call(lambda: (_ for _ in ()).throw(Exception("fail")))
        except Exception: pass
    assert cb.state.value == "open"
    await asyncio.sleep(1.1)
    try:
        await cb.call(lambda: 1)
    except Exception: pass
    assert cb.state.value in {"half_open","closed"}
