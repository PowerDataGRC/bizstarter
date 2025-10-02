from extensions import db
from flask_login import UserMixin
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
class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    description = db.Column(db.String(200), nullable=False)
    price = db.Column(db.Float, nullable=False, default=0.0)
    sales_volume = db.Column(db.Integer, nullable=False, default=0)
    sales_volume_unit = db.Column(db.String(20), nullable=False, default='monthly')
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

    def to_dict(self):
        return {c.name: getattr(self, c.name) for c in self.__table__.columns}

class Expense(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    item = db.Column(db.String(200), nullable=False)
    amount = db.Column(db.Float, nullable=False, default=0.0)
    frequency = db.Column(db.String(20), nullable=False, default='monthly')
    readonly = db.Column(db.Boolean, default=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

    def to_dict(self):
        return {c.name: getattr(self, c.name) for c in self.__table__.columns}

class Asset(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    description = db.Column(db.String(200), nullable=False)
    amount = db.Column(db.Float, nullable=False, default=0.0)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

    def to_dict(self):
        return {c.name: getattr(self, c.name) for c in self.__table__.columns}

class Liability(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    description = db.Column(db.String(200), nullable=False)
    amount = db.Column(db.Float, nullable=False, default=0.0)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

    def to_dict(self):
        return {c.name: getattr(self, c.name) for c in self.__table__.columns}

class FinancialParams(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, unique=True)
    
    company_name = db.Column(db.String(100), default='')
    cogs_percentage = db.Column(db.Float, default=35.0)
    tax_rate = db.Column(db.Float, default=8.0)
    seasonality = db.Column(db.Text, default=json.dumps([1.0] * 12))
    
    # Balance Sheet / Ratios
    current_assets = db.Column(db.Float, default=15000.0)
    current_liabilities = db.Column(db.Float, default=8000.0)
    interest_expense = db.Column(db.Float, default=2000.0)
    depreciation = db.Column(db.Float, default=3000.0)

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

class AssessmentMessage(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    risk_level = db.Column(db.String(50), unique=True, nullable=False)
    status = db.Column(db.String(100), nullable=False)
    caption = db.Column(db.Text, nullable=False)
    status_class = db.Column(db.String(50), nullable=False)
    dscr_status = db.Column(db.Text, nullable=False)

class BusinessStartupActivity(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    activity = db.Column(db.String(200), nullable=False)
    description = db.Column(db.String(500), nullable=False)
    weight = db.Column(db.Integer, nullable=False)
    progress = db.Column(db.Integer, nullable=False, default=0)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

    def __repr__(self):
        return f'<Activity {self.activity}>'