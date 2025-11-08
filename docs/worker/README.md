# Worker Module

The **worker** module provides an entrypoint for a background worker process.  It is used when deploying the Systematic Review Pipeline as part of a Docker Compose stack to handle long‑running tasks independently of the web server.

## Purpose

When the web dashboard initiates a search, screening or analysis job, these operations can take minutes to hours to complete.  Running them on the main FastAPI event loop would block incoming requests.  Instead, a separate worker process can dequeue jobs from a message broker (e.g. Redis, RabbitMQ) and execute them asynchronously.

The current implementation in [`worker.py`](../../src/srp/worker.py) is a stub that simply logs a startup message and sleeps in a loop.  It is intended to be extended with a real task queue consumer.  For example, you could integrate [RQ](https://python-rq.org/) or [Celery](https://docs.celeryq.dev/) to listen for jobs posted by the web server, perform searches or analyses, and update job status in a database.

## Running the worker

In the provided `Dockerfile` and `docker-compose.yml`, a separate service named `worker` is defined.  You can start the worker alongside the web server:

```bash
docker-compose up web worker
```

The worker process will run the `main()` function in `worker.py`, which currently idles.  Modify the body of the loop to poll your task queue and execute tasks accordingly.

## Extending

To implement a functional worker, consider the following steps:

1. Choose a task queue library (e.g. RQ, Celery) and add it to `requirements.txt`.
2. Define serialisable task functions (e.g. `run_search_job`, `run_screening_job`) and register them with the queue.
3. Modify the FastAPI routes to enqueue tasks instead of performing work inline.
4. Replace the idle loop in `worker.py` with a call to the queue’s worker runner (e.g. `rq.Worker.run()`).
5. Persist task results in a database or file system for retrieval by the web server.