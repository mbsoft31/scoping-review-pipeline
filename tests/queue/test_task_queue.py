import pytest
from srp.async_queue.task_queue import TaskQueue, SearchTask, TaskStatus

@pytest.mark.asyncio
async def test_priority_enqueue_dequeue(tmp_path):
    queue = TaskQueue(persist_dir=tmp_path)
    first = SearchTask(source="openalex", query="first", priority=1)
    second = SearchTask(source="openalex", query="second", priority=0)
    await queue.enqueue(first)
    await queue.enqueue(second)
    top = await queue.dequeue()
    assert top.query == "second"  # Lower number is higher priority

@pytest.mark.asyncio
async def test_status_transitions(tmp_path):
    queue = TaskQueue(persist_dir=tmp_path)
    task = SearchTask(source="arxiv", query="queue test", limit=5)
    tid = await queue.enqueue(task)
    tsk = await queue.dequeue()
    assert tsk.status == TaskStatus.RUNNING
    await queue.complete_task(tid, [])
    assert queue.get_task(tid).status == TaskStatus.COMPLETED

@pytest.mark.asyncio
async def test_persistence(tmp_path):
    queue = TaskQueue(persist_dir=tmp_path)
    t = SearchTask(source="openalex", query="persist", limit=3)
    tid = await queue.enqueue(t)
    # Recreate queue object and check task is still there.
    queue2 = TaskQueue(persist_dir=tmp_path)
    assert queue2.get_task(tid).query == "persist"
