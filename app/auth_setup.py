from flask import Flask
from flask_login import LoginManager

from .models import User

def setup_login_manager(app: Flask, lm: LoginManager):
    """Configure the LoginManager for the Flask app."""
    lm.init_app(app)
    lm.login_view = 'auth.login'

    @lm.user_loader
    def load_user(user_id: str) -> User | None:
        return User.query.get(int(user_id))