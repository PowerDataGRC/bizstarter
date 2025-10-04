import os
from main import app
from alembic.config import Config
from alembic import command

with app.app_context():
    try:
        # This will run the database migrations automatically on startup.
        # It uses the Alembic API directly, which is more reliable in serverless
        # environments than calling the 'flask db upgrade' command.
        migrations_dir = os.path.join(os.path.dirname(__file__), 'migrations')
        alembic_cfg = Config(os.path.join(migrations_dir, "alembic.ini"))
        alembic_cfg.set_main_option('script_location', migrations_dir)
        alembic_cfg.set_main_option('sqlalchemy.url', app.config['SQLALCHEMY_DATABASE_URI'])
        command.upgrade(alembic_cfg, "head")
    except Exception as e:
        # Log any migration errors to the Vercel logs
        app.logger.error(f"Failed to apply database migrations: {e}")