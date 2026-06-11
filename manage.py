from django.core.management import execute_from_command_line
import os
import sys

from opentelemetry.instrumentation.django import DjangoInstrumentor

if __name__ == "__main__":
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    # Collect OpenTelemetry application metrics
    DjangoInstrumentor().instrument()
    execute_from_command_line(sys.argv)
