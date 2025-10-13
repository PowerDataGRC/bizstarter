import os
import json
import logging
from dotenv import load_dotenv
from flask import Flask, current_app
from flask_migrate import Migrate
import click
from alembic.config import Config
from alembic import command

from .extensions import db, login_manager
from .database import get_assessment_messages


def create_app():
    load_dotenv()
    
    """Create and configure an instance of the Flask application."""
    # The root path of the app is the 'app' directory. The templates are one level up.
    template_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'templates'))
    app = Flask(
        __name__,
        instance_relative_config=True,
        template_folder=template_dir,
        static_folder=os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'static'))
    )
    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', os.urandom(24))
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

    # --- Database Configuration ---
    prod_db_url = os.environ.get('DATABASE_URL') or os.environ.get('POSTGRES_URL')
    local_db_url = os.environ.get('LOCAL_DATABASE_URL')
    if prod_db_url:
        prod_db_url = prod_db_url.replace("postgres://", "postgresql://")
        if 'sslmode' not in prod_db_url:
            prod_db_url += "?sslmode=require"
        app.config['SQLALCHEMY_DATABASE_URI'] = prod_db_url
        app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
            "pool_pre_ping": True,
            "pool_recycle": 300,
            "connect_args": {"connect_timeout": 30}
        }
    elif local_db_url:
        app.config['SQLALCHEMY_DATABASE_URI'] = local_db_url
    else:
        # Local development with SQLite
        # Use /tmp for serverless environments like Vercel, or instance folder for local
        db_path = os.path.join('/tmp', 'bizstarter.db') if 'VERCEL' in os.environ else \
                  os.path.join(app.instance_path, 'bizstarter.db')
        app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{db_path}'

    # --- Logging Configuration ---
    if not app.debug and not app.testing:
        # In production, log to stderr.
        handler = logging.StreamHandler()
        handler.setLevel(logging.INFO)
        app.logger.addHandler(handler)

    # Initialize extensions
    db.init_app(app)
    Migrate(app, db)

    @app.teardown_appcontext
    def shutdown_session(exception=None):
        """Remove the database session at the end of the request or app context."""
        db.session.remove()

    @app.after_request
    def after_request_func(response):
        """Ensure responses aren't cached, useful for development."""
        if app.debug:
            response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
            response.headers["Pragma"] = "no-cache"
            response.headers["Expires"] = "0"
            response.headers['Cache-Control'] = 'public, max-age=0'
        return response

    # Register custom template filter
    @app.template_filter('fromjson')
    def fromjson_filter(value):
        return json.loads(value)

    # Register Blueprints
    from . import auth
    from . import main_routes

    # --- Configure Flask-Login ---
    login_manager.init_app(app)
    from .models import User
    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    app.register_blueprint(auth.bp)
    app.register_blueprint(main_routes.bp)

    # Register CLI commands
    app.cli.add_command(init_db_command)

    return app

def seed_initial_data():
    """Seeds the database with initial data."""
    from .models import AssessmentMessage
    print("Seeding assessment_messages table...")
    try:
        with current_app.open_resource('../assessment_messages.json') as f:
            messages_data = json.load(f)
            for risk_level, data in messages_data.items():
                # Check if a message for this risk level already exists
                existing_message = AssessmentMessage.query.filter_by(risk_level=risk_level).first()
                if not existing_message:
                    print(f"  - Adding message for '{risk_level}'...")
                    message = AssessmentMessage(
                        risk_level=risk_level,
                        status=data['status'],
                        caption=data['caption'],
                        status_class=data['status_class'],
                        dscr_status=data['dscr_status']
                    )
                    db.session.add(message)
            db.session.commit()
            print("Assessment messages seeding complete.")
    except Exception as e:
        print(f"Error seeding assessment messages: {e}")
        db.session.rollback()

@click.command('init-db')
def init_db_command():
    """Clear the existing data and create new tables."""
    with current_app.app_context():
        click.echo("Applying database migrations...")
        try:
            migrations_dir = os.path.join(os.path.dirname(current_app.root_path), 'migrations')
            alembic_cfg = Config(os.path.join(migrations_dir, "alembic.ini"))
            alembic_cfg.set_main_option("script_location", migrations_dir)
            alembic_cfg.set_main_option('sqlalchemy.url', current_app.config['SQLALCHEMY_DATABASE_URI'])
            command.upgrade(alembic_cfg, 'head')
            click.echo("Database migrations applied successfully.")
            seed_initial_data()
        except Exception as e:
            click.echo(f"Error applying migrations: {e}", err=True)