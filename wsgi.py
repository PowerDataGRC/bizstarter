import os
from main import app
from app.extensions import db
from alembic.config import Config
from alembic import command

with app.app_context():
    try:
        migrations_dir = os.path.join(os.path.dirname(__file__), 'migrations')
        alembic_cfg = Config(os.path.join(migrations_dir, "alembic.ini"))
        alembic_cfg.set_main_option('script_location', migrations_dir)
        alembic_cfg.set_main_option('sqlalchemy.url', app.config['SQLALCHEMY_DATABASE_URI'])
        alembic_cfg.attributes['target_metadata'] = db.metadata
        command.upgrade(alembic_cfg, "head")
    except Exception as e:
        # Log any migration errors to the Vercel logs
        app.logger.error(f"Failed to apply database migrations: {e}")