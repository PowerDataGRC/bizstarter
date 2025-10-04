from flask import Blueprint, render_template, request, redirect, url_for, flash
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
        initial_activities = [
            {'activity': 'Conduct Market Research', 'description': 'Analyze competitors and demand', 'weight': 10, 'progress': 0},
            # ... (add all other activities here for brevity)
            {'activity': 'Prepare Operational & Privacy Policies', 'description': 'SOPs, data/privacy, contracts, legal docs', 'weight': 5, 'progress': 0}
        ]
        initial_expenses = [
            Expense(item='Rent/Lease', amount=1200.0, frequency='monthly', user_id=new_user.id),
            # ... (add all other expenses here)
            Expense(item='Legal', amount=100.0, frequency='monthly', user_id=new_user.id),
        ]
        initial_assets = [
            Asset(description='Cash & Equivalents', amount=10000.0, user_id=new_user.id),
            Asset(description='Inventory', amount=5000.0, user_id=new_user.id),
            Asset(description='Equipment', amount=35000.0, user_id=new_user.id)
        ]
        initial_liabilities = [
            Liability(description='Credit Card Debt', amount=5000.0, user_id=new_user.id),
            Liability(description='Bank Loan', amount=20000.0, user_id=new_user.id)
        ]
        initial_products = [Product(description='', price=0.0, sales_volume=0, sales_volume_unit='monthly', user_id=new_user.id) for _ in range(4)]

        db.session.add(FinancialParams(user_id=new_user.id))
        db.session.add_all([BusinessStartupActivity(**item, user_id=new_user.id) for item in initial_activities])
        db.session.add_all(initial_expenses)
        db.session.add_all(initial_assets)
        db.session.add_all(initial_liabilities)
        db.session.add_all(initial_products)
        db.session.commit()

        flash('Registration successful! Please log in.')
        return redirect(url_for('auth.login'))
    return render_template('register.html')

@bp.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('auth.login'))