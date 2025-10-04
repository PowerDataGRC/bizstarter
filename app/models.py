from app.extensions import db
from flask_login import UserMixin
from sqlalchemy import inspect
import json

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)

    # Relationships
    products = db.relationship('Product', backref='user', lazy=True, cascade="all, delete-orphan")
    expenses = db.relationship('Expense', backref='user', lazy=True, cascade="all, delete-orphan")
    assets = db.relationship('Asset', backref='user', lazy=True, cascade="all, delete-orphan")
    liabilities = db.relationship('Liability', backref='user', lazy=True, cascade="all, delete-orphan")
    financial_params = db.relationship('FinancialParams', backref='user', uselist=False, cascade="all, delete-orphan")

    startup_activities = db.relationship('BusinessStartupActivity', backref='user', lazy=True, cascade="all, delete-orphan")

    def __init__(self, username: str, password_hash: str):
        self.username = username
        self.password_hash = password_hash

class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    description = db.Column(db.String(200), nullable=False)
    price = db.Column(db.Float, nullable=False, default=0.0)
    sales_volume = db.Column(db.Integer, nullable=False, default=0)
    sales_volume_unit = db.Column(db.String(20), nullable=False, default='monthly')
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

    def __init__(self, description, price, sales_volume, sales_volume_unit, user_id):
        self.description = description
        self.price = price
        self.sales_volume = sales_volume
        self.sales_volume_unit = sales_volume_unit
        self.user_id = user_id

    def to_dict(self):
        insp = inspect(self)
        if insp is None:
            return {}
        return {c.key: getattr(self, c.key) for c in insp.mapper.column_attrs}

class Expense(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    item = db.Column(db.String(200), nullable=False)
    amount = db.Column(db.Float, nullable=False, default=0.0)
    frequency = db.Column(db.String(20), nullable=False, default='monthly')
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

    def __init__(self, item, amount, frequency, user_id):
        self.item = item
        self.amount = amount
        self.frequency = frequency
        self.user_id = user_id

    def to_dict(self):
        insp = inspect(self)
        if insp is None:
            return {}
        return {c.key: getattr(self, c.key) for c in insp.mapper.column_attrs}

class Asset(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    description = db.Column(db.String(200), nullable=False)
    amount = db.Column(db.Float, nullable=False, default=0.0)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

    def __init__(self, description, amount, user_id):
        self.description = description
        self.amount = amount
        self.user_id = user_id

    def to_dict(self):
        insp = inspect(self)
        if insp is None:
            return {}
        return {c.key: getattr(self, c.key) for c in insp.mapper.column_attrs}

class Liability(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    description = db.Column(db.String(200), nullable=False)
    amount = db.Column(db.Float, nullable=False, default=0.0)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

    def __init__(self, description, amount, user_id):
        self.description = description
        self.amount = amount
        self.user_id = user_id

    def to_dict(self):
        insp = inspect(self)
        if insp is None:
            return {}
        return {c.key: getattr(self, c.key) for c in insp.mapper.column_attrs}

class FinancialParams(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, unique=True)
    
    company_name = db.Column(db.String(100), default='')
    cogs_percentage = db.Column(db.Float, default=35.0)
    tax_rate = db.Column(db.Float, default=8.0)
    seasonality = db.Column(db.Text, default=json.dumps([1.0] * 12))
    
    # Balance Sheet / Ratios
    current_assets = db.Column(db.Float, nullable=False, default=15000.0)
    current_liabilities = db.Column(db.Float, nullable=False, default=8000.0)
    interest_expense = db.Column(db.Float, nullable=False, default=2000.0)
    depreciation = db.Column(db.Float, nullable=False, default=3000.0)

    # Calculated values for loan calculator
    quarterly_net_profit = db.Column(db.Float, default=0.0)
    annual_net_profit = db.Column(db.Float, default=0.0)
    total_annual_revenue = db.Column(db.Float, default=0.0)
    net_operating_income = db.Column(db.Float, default=0.0)
    annual_operating_expenses = db.Column(db.Float, default=0.0)

    # Loan details could also be stored here if it's a one-to-one relationship
    loan_amount = db.Column(db.Float, nullable=True)
    loan_interest_rate = db.Column(db.Float, nullable=True)
    loan_term = db.Column(db.Integer, nullable=True)
    loan_monthly_payment = db.Column(db.Float, nullable=True)
    loan_schedule = db.Column(db.Text, nullable=True)

    def __init__(self, user_id):
        self.user_id = user_id

class AssessmentMessage(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    risk_level = db.Column(db.String(50), unique=True, nullable=False)
    status = db.Column(db.String(100), nullable=False)
    caption = db.Column(db.Text, nullable=False)
    status_class = db.Column(db.String(50), nullable=False)
    dscr_status = db.Column(db.Text, nullable=False)

    def __init__(self, risk_level, status, caption, status_class, dscr_status):
        self.risk_level = risk_level
        self.status = status
        self.caption = caption
        self.status_class = status_class
        self.dscr_status = dscr_status

class BusinessStartupActivity(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    activity = db.Column(db.String(200), nullable=False)
    description = db.Column(db.String(500), nullable=False)
    weight = db.Column(db.Integer, nullable=False)
    progress = db.Column(db.Integer, nullable=False, default=0)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

    def __init__(self, activity, description, weight, progress, user_id):
        self.activity = activity
        self.description = description
        self.weight = weight
        self.progress = progress
        self.user_id = user_id

    def __repr__(self):
        return f'<Activity {self.activity}>'