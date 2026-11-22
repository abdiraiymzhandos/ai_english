"""Poll both durable queues in one process, with independent database connections."""
import logging
import signal
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from io import StringIO
from threading import Event

from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.db import connection, connections

logger = logging.getLogger(__name__)


def poll(command, limit, interval, stopping):
    while not stopping.is_set():
        output = StringIO()
        try:
            call_command(command, limit=limit, stdout=output, stop_requested=stopping.is_set)
            count = int(output.getvalue().strip())
            if count:
                logger.info('%s processed %d', command, count)
        except Exception as exc:
            # Driver and network exception messages may contain private connection details.
            logger.error('%s failed (%s)', command, type(exc).__name__)
        finally:
            try:
                connections.close_all()
            except Exception as exc:
                logger.error('%s connection cleanup failed (%s)', command, type(exc).__name__)
        # Interruptible relative wait, independent of wall-clock and timezone changes.
        if stopping.wait(interval):
            break


class Command(BaseCommand):
    help = 'Continuously process registration alerts and analytics in one Always-on Task.'

    def add_arguments(self, parser):
        parser.add_argument('--notification-interval', type=int, default=15, help='Seconds between alert batches.')
        parser.add_argument('--analytics-interval', type=int, default=60, help='Seconds between analytics batches.')
        parser.add_argument('--notification-limit', type=int, default=100)
        parser.add_argument('--analytics-limit', type=int, default=5000)
        parser.add_argument('--allow-sqlite', action='store_true', help='Allow an explicitly selected local SQLite database.')

    def handle(self, *args, **options):
        vendor = connection.vendor
        if vendor != 'mysql' and not (vendor == 'sqlite' and options['allow_sqlite']):
            raise CommandError('MySQL is required. Use --allow-sqlite only for local testing.')
        schedules = [
            ('process_registration_notifications', options['notification_limit'], options['notification_interval']),
            ('process_analytics', options['analytics_limit'], options['analytics_interval']),
        ]
        if any(min(limit, interval) < 1 for _, limit, interval in schedules):
            raise CommandError('Intervals and limits must be positive integers.')

        stopping = Event()

        def request_stop(signum, frame):
            stopping.set()

        previous = {sig: signal.signal(sig, request_stop) for sig in (signal.SIGTERM, signal.SIGINT)}
        try:
            logger.info('OqyAI background worker started (%s)', vendor)
            with ThreadPoolExecutor(max_workers=2, thread_name_prefix='oqyai') as pool:
                futures = [pool.submit(poll, command, limit, interval, stopping)
                           for command, limit, interval in schedules]
                try:
                    done, _ = wait(futures, return_when=FIRST_COMPLETED)
                    for future in done:
                        future.result()
                finally:
                    stopping.set()
        finally:
            for sig, handler in previous.items():
                signal.signal(sig, handler)
            logger.info('OqyAI background worker stopped')
