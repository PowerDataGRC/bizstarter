import json
from flask import current_app
from .extensions import db, login_manager
from sqlalchemy import delete
from .models import User, Product, Expense, Asset, Liability, FinancialParams, BusinessStartupActivity
from logic.profitability import calculate_profitability
from logic.financial_ratios import calculate_key_ratios
from .auth import _seed_initial_user_data

def get_product_and_expense_data(user_id):
    """
    Fetches product and expense data for a user.
    Includes self-healing logic to re-seed data if it's incomplete.
    """
    user = db.session.get(User, user_id)
    if not user:
        return [], [], ''

    # Self-healing: If the user has an incomplete or empty expense list, re-seed all their data.
    if len(user.expenses) < 4:
        current_app.logger.info(f"User {user.id} has an incomplete data set. Re-seeding.")
        db.session.execute(delete(Product).where(Product.user_id == user.id))
        db.session.execute(delete(Expense).where(Expense.user_id == user.id))
        db.session.execute(delete(Asset).where(Asset.user_id == user.id))
        db.session.execute(delete(Liability).where(Liability.user_id == user.id))
        db.session.execute(delete(BusinessStartupActivity).where(BusinessStartupActivity.user_id == user.id))
        db.session.execute(delete(FinancialParams).where(FinancialParams.user_id == user.id))
        db.session.commit()
        _seed_initial_user_data(user.id)

    products_dict = [p.to_dict() for p in user.products]
    expenses_dict = [e.to_dict() for e in user.expenses]
    company_name = user.financial_params.company_name if user.financial_params is not None else ''
    return products_dict, expenses_dict, company_name

def save_product_and_expense_data(user_id, data):
    """Saves product, expense, and company name data for a user."""
    db.session.execute(delete(Product).where(Product.user_id == user_id))
    db.session.execute(delete(Expense).where(Expense.user_id == user_id))

    for p_data in data.get('products', []):
        try:
            db.session.add(Product(
                description=p_data.get('description'), price=float(p_data.get('price', 0) or 0),
                sales_volume=int(p_data.get('sales_volume', 0) or 0),
                sales_volume_unit=p_data.get('sales_volume_unit', 'monthly'), user_id=user_id
            ))
        except (ValueError, TypeError):
            continue

    for e_data in data.get('expenses', []):
        try:
            db.session.add(Expense(
                item=e_data.get('item'), amount=float(e_data.get('amount', 0) or 0),
                frequency=e_data.get('frequency', 'monthly'), user_id=user_id
            ))
        except (ValueError, TypeError):
            continue

    user = db.session.get(User, user_id)
    if not user:
        return # Or handle error appropriately
    financial_params = user.financial_params if user.financial_params is not None else FinancialParams(user_id=user_id)
    financial_params.company_name = data.get('company_name', '')
    db.session.add(financial_params)
    db.session.commit()

def get_or_recalculate_forecast(user, data=None):
    """
    Calculates a financial forecast. If data is provided, it updates parameters
    before recalculating. Otherwise, it uses existing parameters.
    """
    if not user:
        return None
    params = user.financial_params
    products = [p.to_dict() for p in user.products]

    if data:  # Recalculating with new data
        params.cogs_percentage = float(data.get('cogs_percentage'))
        params.tax_rate = float(data.get('tax_rate'))
        params.seasonality = json.dumps([float(v) for v in data.get('seasonality', [1.0] * 12)])
        params.current_assets = float(data.get('current_assets'))
        params.current_liabilities = float(data.get('current_liabilities'))
        params.interest_expense = float(data.get('interest_expense'))
        params.depreciation = float(data.get('depreciation'))
        params.annual_operating_expenses = float(data.get('annual_operating_expenses'))
    
    annual_op_ex = params.annual_operating_expenses

    forecast = calculate_profitability(
        products=products, cogs_percentage=params.cogs_percentage,
        annual_operating_expenses=annual_op_ex, tax_rate=params.tax_rate,
        seasonality_factors=json.loads(params.seasonality)
    )

    total_assets = sum(a.amount for a in user.assets)
    total_debt = sum(l.amount for l in user.liabilities)
    net_operating_income = forecast['annual']['gross_profit'] - annual_op_ex

    annual_ratios = calculate_key_ratios(
        net_profit=forecast['annual']['net_profit'], total_revenue=forecast['annual']['revenue'],
        total_assets=total_assets, current_assets=params.current_assets,
        current_liabilities=params.current_liabilities, total_debt=total_debt,
        net_operating_income=net_operating_income, interest_expense=params.interest_expense,
        depreciation=params.depreciation
    )
    forecast['annual'].update(annual_ratios)
    forecast['quarterly'].update(annual_ratios)

    # Persist key results
    params.total_annual_revenue = forecast['annual']['revenue']
    params.annual_net_profit = forecast['annual']['net_profit']
    params.quarterly_net_profit = forecast['quarterly']['net_profit']
    params.net_operating_income = net_operating_income
    params.net_operating_income = net_operating_income
    db.session.commit()

    return forecast