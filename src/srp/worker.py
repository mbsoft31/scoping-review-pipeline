"""Background worker for the SRP Docker deployment.

This module defines an entry point for a worker process that could
handle long-running tasks such as searches and analyses outside of
the web server.  In this minimal implementation the worker will
simply idle; you can extend it to consume tasks from a queue or
database in future releases.
"""

import time
import logging


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="[%(asctime)s] %(levelname)s %(message)s")
    logging.info("SRP worker started.")
    try:
        while True:
            # In a real worker, poll for jobs and execute them here
            time.sleep(60)
    except KeyboardInterrupt:
        logging.info("SRP worker stopping...")


if __name__ == "__main__":
    main()