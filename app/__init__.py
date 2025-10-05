import os
import json
from flask import Flask
from flask_migrate import Migrate
import click

from .extensions import db, login_manager

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
        # Use /tmp for serverless environments like Vercel, or instance folder for local
        db_path = os.path.join('/tmp', 'bizstarter.db') if 'VERCEL' in os.environ else \
                  os.path.join(app.instance_path, 'bizstarter.db')
        app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{db_path}'

    # Initialize extensions
    db.init_app(app)
    Migrate(app, db)

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
    if not AssessmentMessage.query.first():
        print("Seeding assessment_messages table...")
        try:
            with current_app.open_resource('../assessment_messages.json') as f:
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