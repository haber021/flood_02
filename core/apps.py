from django.apps import AppConfig
import threading
import time
import os
import sys
from django.core.management import call_command


class CoreConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'core'

    _weather_thread_started = False

    def ready(self):
        """
        Start a background thread that periodically runs the
        `fetch_real_weather` management command while the server process is alive.

        Notes:
        - Guarded to avoid duplicate starts across Django's autoreload and multiple imports.
        - Interval can be overridden via env WEATHER_UPDATE_INTERVAL (seconds).
        - For production-grade scheduling or multi-worker deployments, prefer Celery beat
          or an OS scheduler to avoid multiple concurrent runs.
        """
        # Only start when running the dev server or common runserver variants
        server_commands = {'runserver', 'runserver_plus'}
        is_server_cmd = any(cmd in sys.argv for cmd in server_commands)

        # Avoid starting in the autoreloader parent process
        is_main = os.environ.get('RUN_MAIN') == 'true'

        if not (is_server_cmd and is_main):
            return

        if CoreConfig._weather_thread_started:
            return
        CoreConfig._weather_thread_started = True

        interval = int(os.environ.get('WEATHER_UPDATE_INTERVAL', 120*60))  # default 15 minutes

        def worker():
            # Slight delay on startup to allow migrations/connections to settle
            time.sleep(10)
            while True:
                try:
                    call_command('fetch_real_weather')
                except Exception as e:
                    print('[weather-updater] Error:', e)
                # Sleep until next run (minimum 60 seconds)
                time.sleep(max(60, interval))

        t = threading.Thread(target=worker, name='weather-updater', daemon=True)
        t.start()
