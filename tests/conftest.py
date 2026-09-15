import logging
import os

logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)

# Force an empty Sentry DSN so tests never report to a real project
os.environ["SENTRY_DSN"] = ""
