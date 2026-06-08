"""
Dev helper: runs agent check every N seconds in a loop.
Replaces Celery Beat/Worker for local development — no Redis required.

Usage:
    python run_agent_loop.py            # default: every 60 seconds
    python run_agent_loop.py 120        # every 2 minutes
    python run_agent_loop.py 30         # every 30 seconds (for quick testing)
"""
import os
import sys
import time
import logging

# Add backend dir to path and set Django settings
sys.path.insert(0, os.path.dirname(__file__))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

import django
django.setup()

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s %(name)s %(message)s',
    datefmt='%H:%M:%S',
)
logger = logging.getLogger('agent_loop')

from apps.leads.agent_service import agent_service

INTERVAL = int(sys.argv[1]) if len(sys.argv) > 1 else 60


def main():
    logger.info(f'Agent loop started — checking every {INTERVAL}s. Ctrl+C to stop.')
    while True:
        try:
            results = agent_service.run_agent_check()
            messaged = results.get('messaged', 0)
            if messaged:
                logger.info(f'Agent check done: {results}')
            else:
                logger.debug(f'Agent check done: {results}')
        except Exception as exc:
            logger.error(f'Agent check error: {exc}', exc_info=True)
        time.sleep(INTERVAL)


if __name__ == '__main__':
    main()
