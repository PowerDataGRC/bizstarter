import os
import json
from flask import Flask
from flask_migrate import Migrate
import click

from .extensions import db, login_manager
from .models import User, AssessmentMessage


def create_app():
    """Create and configure an instance of the Flask application."""
    app = Flask(
        __name__,
        instance_relative_config=True,
        template_folder='../templates'
    )
    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', os.urandom(24))
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

    # --- Database Configuration ---
    prod_db_url = os.environ.get('DATABASE_URL') or os.environ.get('POSTGRES_URL')
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
    else:
        # Local development with SQLite
        instance_path = os.path.join(os.path.dirname(app.root_path), 'instance')
        os.makedirs(instance_path, exist_ok=True)
        app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{os.path.join(instance_path, "bizstarter.db")}'

    # Initialize extensions
    db.init_app(app)
    Migrate(app, db)

    # Configure Flask-Login
    from .auth_setup import setup_login_manager
    setup_login_manager(app, lm=login_manager)

    # Register custom template filter
    @app.template_filter('fromjson')
    def fromjson_filter(value):
        return json.loads(value)

    # Register Blueprints
    from . import auth
    app.register_blueprint(auth.bp)

    from . import main_routes
    app.register_blueprint(main_routes.bp)

    # Register CLI commands
    app.cli.add_command(init_db_command)

    return app

def seed_initial_data():
    """Seeds the database with initial data."""
    if not AssessmentMessage.query.first():
        print("Seeding assessment_messages table...")
        try:
            json_path = os.path.join(os.path.dirname(__file__), '..', 'assessment_messages.json')
            with open(json_path, 'r') as f:
                messages_data = json.load(f)
                for risk_level, data in messages_data.items():
                    message = AssessmentMessage(
                        risk_level=risk_level,
                        status=data['status'],
                        caption=data['caption'],
                        status_class=data['status_class'],
                        dscr_status=data['dscr_status']
                    )
                    db.session.add(message)
                db.session.commit()
                print("Assessment messages seeded successfully.")
        except Exception as e:
            print(f"Error seeding assessment messages: {e}")
            db.session.rollback()

@click.command('init-db')
def init_db_command():
    """Clear the existing data and create new tables."""
    db.create_all()
    seed_initial_data()
    click.echo('Initialized the database.')