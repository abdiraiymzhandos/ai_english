from django.core.management.base import BaseCommand

from lessons.services.live_explanations import execute_next


class Command(BaseCommand):
    stealth_options = ("stop_requested",)
    help = "Process pending private Live narrations once; each job has one paid attempt."

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=1)

    def handle(self, *args, **options):
        stopping = options.get("stop_requested") or (lambda: False)
        count = 0
        while count < options["limit"] and not stopping() and execute_next():
            count += 1
        self.stdout.write(str(count))
