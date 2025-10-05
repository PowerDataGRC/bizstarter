import os
import sys
import logging
from main import app
from alembic.config import Config
from alembic import command

try:
    with app.app_context():
        print("Attempting to run database migrations...")
        migrations_dir = os.path.join(os.path.dirname(__file__), 'migrations')
        alembic_cfg = Config(os.path.join(migrations_dir, "alembic.ini"))
        alembic_cfg.set_main_option('script_location', migrations_dir)
        alembic_cfg.set_main_option('sqlalchemy.url', app.config['SQLALCHEMY_DATABASE_URI'])
        command.upgrade(alembic_cfg, "head")
        print("Database migrations completed successfully.")
except Exception as e:
    logging.basicConfig(stream=sys.stdout, level=logging.ERROR)
    logging.error("Failed to apply database migrations on startup:", exc_info=e)