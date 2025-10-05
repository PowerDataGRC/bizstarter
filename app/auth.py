import json
from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import login_user, logout_user, current_user

from .models import User, Expense, Asset, Liability, FinancialParams, BusinessStartupActivity, Product
from .extensions import db

bp = Blueprint('auth', __name__, url_prefix='/')

@bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('main.intro'))
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = User.query.filter_by(username=username).first()
        if user and password and check_password_hash(user.password_hash, password):
            login_user(user, remember=True)
            return redirect(url_for('main.intro'))
        else:
            flash('Invalid username or password.', 'danger')
    return render_template('login.html')

@bp.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('main.intro'))
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        if not username or not password:
            flash('Username and password are required.')
            return render_template('register.html')

        if User.query.filter_by(username=username).first():
            flash('Username already exists. Please choose a different one.')
            return render_template('register.html')

        new_user = User(
            username=username,
            password_hash=generate_password_hash(password, method='pbkdf2:sha256')
        )
        db.session.add(new_user)
        db.session.commit()

        # --- Seed all initial data for the new user ---
        _seed_initial_user_data(new_user.id)


        flash('Registration successful! Please log in.')
        return redirect(url_for('auth.login'))
    return render_template('register.html')

def _seed_initial_user_data(user_id):
    """Seeds the database with a default set of data for a new user."""
    try:
        with current_app.open_resource('../startup_activities.json') as f:
            initial_activities_data = json.load(f)
        
        initial_activities = [BusinessStartupActivity(**item, user_id=user_id) for item in initial_activities_data]

        initial_expenses = [
            Expense(item='Rent/Lease', amount=1200.0, frequency='monthly', user_id=user_id),
            Expense(item='Salaries and Wages', amount=5000.0, frequency='monthly', user_id=user_id),
            Expense(item='Utilities (Electricity, Water, Internet)', amount=400.0, frequency='monthly', user_id=user_id),
            Expense(item='Marketing and Advertising', amount=600.0, frequency='monthly', user_id=user_id),
            Expense(item='Software & Subscriptions', amount=150.0, frequency='monthly', user_id=user_id),
            Expense(item='Insurance', amount=200.0, frequency='monthly', user_id=user_id),
            Expense(item='Legal & Accounting', amount=250.0, frequency='monthly', user_id=user_id),
            Expense(item='Office Supplies', amount=100.0, frequency='monthly', user_id=user_id)
        ]
        initial_products = [Product(description='', price=0.0, sales_volume=0, sales_volume_unit='monthly', user_id=user_id) for _ in range(4)]
        initial_assets = [
            Asset(description='Cash & Equivalents', amount=10000.0, user_id=user_id),
            Asset(description='Inventory', amount=5000.0, user_id=user_id),
            Asset(description='Equipment', amount=35000.0, user_id=user_id)
        ]
        initial_liabilities = [
            Liability(description='Credit Card Debt', amount=5000.0, user_id=user_id),
            Liability(description='Bank Loan', amount=20000.0, user_id=user_id)
        ]

        db.session.add(FinancialParams(user_id=user_id))
        db.session.add_all(initial_activities)
        db.session.add_all(initial_expenses)
        db.session.add_all(initial_products)
        db.session.add_all(initial_assets)
        db.session.add_all(initial_liabilities)
        db.session.commit()
        current_app.logger.info(f"Successfully seeded initial data for new user {user_id}.")
    except Exception as e:
        current_app.logger.error(f"Failed to seed initial data for new user {user_id}: {e}")
        db.session.rollback()

@bp.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('auth.login'))