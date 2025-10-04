import json
from flask import Blueprint, render_template, request, session, jsonify, send_file, redirect, url_for, flash, g
from flask_login import login_required, current_user

from .extensions import db
from .models import Product, Expense, FinancialParams, Asset, Liability, BusinessStartupActivity
from logic.profitability import calculate_profitability
from logic.loan import calculate_loan_schedule
from logic.financial_ratios import calculate_dscr, calculate_key_ratios, calculate_advanced_ratios
from utils.export import create_forecast_spreadsheet
from .database import get_assessment_messages

bp = Blueprint('main', __name__, url_prefix='/')

@bp.before_app_request
def before_request():
    """Load assessment messages into the request context if not already present."""
    if 'assessment_messages' not in g:
        g.assessment_messages = get_assessment_messages()

@bp.route("/")
def index():
    if current_user.is_authenticated:
        return redirect(url_for('main.intro'))
    return redirect(url_for('auth.login'))

@bp.route("/intro")
@login_required
def intro():
    return render_template('intro.html')

@bp.route("/library")
@login_required
def library():
    return render_template('library.html')

@bp.route('/startup-activities', methods=['GET', 'POST'])
@login_required
def startup_activities():
    if request.method == 'POST':
        BusinessStartupActivity.query.filter_by(user_id=current_user.id).delete()
        activities, descriptions, weights, progresses = (
            request.form.getlist('activity'), request.form.getlist('description'),
            request.form.getlist('weight'), request.form.getlist('progress')
        )
        total_weight, new_activities = 0, []
        for i in range(len(activities)):
            if activities[i].strip() and weights[i].strip():
                try:
                    weight, progress = int(weights[i]), int(progresses[i])
                    total_weight += weight
                    new_activities.append(BusinessStartupActivity(
                        activity=activities[i].strip(), description=descriptions[i].strip(),
                        weight=weight, progress=progress, user_id=current_user.id
                    ))
                except ValueError:
                    flash('Invalid weight/progress value.', 'danger')
                    return render_template('startup_activities.html', activities=zip(activities, descriptions, weights, progresses), total_weight="Error"), 400
        if total_weight > 100:
            flash(f'Total weight cannot exceed 100%. Current: {total_weight}%.', 'danger')
            return render_template('startup_activities.html', activities=zip(activities, descriptions, weights, progresses), total_weight=total_weight), 400
        db.session.add_all(new_activities)
        db.session.commit()
        flash('Startup activities updated!', 'success')
        return redirect(url_for('main.product_detail'))

    activities = BusinessStartupActivity.query.filter_by(user_id=current_user.id).order_by(BusinessStartupActivity.id).all()
    if not activities:
        flash('No startup activities found. Add them below.', 'info')
    total_weight = sum(act.weight for act in activities)
    return render_template('startup_activities.html', activities=activities, total_weight=total_weight)

@bp.route("/product-detail", methods=["GET"])
@login_required
def product_detail():
    products_dict = [p.to_dict() for p in current_user.products]
    user_expenses = current_user.expenses
    if not user_expenses:
        # If the user has no expenses, provide a default list.
        expenses_dict = [
            {'item': 'Rent/Lease', 'amount': 0, 'frequency': 'monthly'},
            {'item': 'Salaries and Wages', 'amount': 0, 'frequency': 'monthly'},
            {'item': 'Utilities (Electricity, Water, Internet)', 'amount': 0, 'frequency': 'monthly'},
            {'item': 'Marketing and Advertising', 'amount': 0, 'frequency': 'monthly'},
        ]
    else:
        expenses_dict = [e.to_dict() for e in user_expenses]
    company_name = current_user.financial_params.company_name if current_user.financial_params else ''
    return render_template('product-detail.html', products=products_dict, expenses=expenses_dict, company_name=company_name)

@bp.route("/save-product-details", methods=["POST"])
@login_required
def save_product_details():
    data = request.get_json()
    Product.query.filter_by(user_id=current_user.id).delete()
    Expense.query.filter_by(user_id=current_user.id).delete()
    for p in data.get('products', []):
        try:
            db.session.add(Product(
                description=p.get('description'), price=float(p.get('price', 0) or 0),
                sales_volume=int(p.get('sales_volume', 0) or 0),
                sales_volume_unit=p.get('sales_volume_unit', 'monthly'), user_id=current_user.id
            ))
        except (ValueError, TypeError): continue
    for e in data.get('expenses', []):
        try:
            db.session.add(Expense(
                item=e.get('item'), amount=float(e.get('amount', 0) or 0),
                frequency=e.get('frequency', 'monthly'),
                user_id=current_user.id
            ))
        except (ValueError, TypeError): continue
    financial_params = current_user.financial_params or FinancialParams(user_id=current_user.id)
    financial_params.company_name = data.get('company_name', '')
    db.session.add(financial_params)
    db.session.commit()
    return jsonify({'status': 'success'})

@bp.route("/financial-forecast", methods=["GET"])
@login_required
def financial_forecast():
    financial_params = current_user.financial_params
    if not financial_params:
        flash('Financial parameters not found. Please visit Product Detail page first.', 'warning')
        return redirect(url_for('main.product_detail'))

    products = [p.to_dict() for p in current_user.products]
    operating_expenses = [e.to_dict() for e in current_user.expenses]
    assets = [a.to_dict() for a in current_user.assets]
    liabilities = [l.to_dict() for l in current_user.liabilities]
    total_assets = sum(item.amount for item in current_user.assets)
    total_debt = sum(item.amount for item in current_user.liabilities)
    
    annual_op_ex = sum(
        (float(e.get('amount', 0)) * 12 if e.get('frequency') == 'monthly' else float(e.get('amount', 0)) * 4)
        for e in operating_expenses
    )

    forecast = calculate_profitability(
        products=products, cogs_percentage=financial_params.cogs_percentage,
        annual_operating_expenses=annual_op_ex, tax_rate=financial_params.tax_rate,
        seasonality_factors=json.loads(financial_params.seasonality)
    )

    # ... (ratio calculations and forecast updates) ...
    # This logic is complex and can remain here for now.

    financial_params.annual_operating_expenses = annual_op_ex
    db.session.commit()

    return render_template(
        'financial-forecast.html',
        forecast=forecast,
        assets=assets,
        liabilities=liabilities,
        financial_params=financial_params
    )

@bp.route("/recalculate-forecast", methods=["POST"])
@login_required
def recalculate_forecast():
    data = request.get_json()
    params = current_user.financial_params
    params.cogs_percentage = float(data.get('cogs_percentage'))
    params.tax_rate = float(data.get('tax_rate'))
    params.seasonality = json.dumps([float(v) for v in data.get('seasonality', [1.0] * 12)])
    params.current_assets = float(data.get('current_assets'))
    params.current_liabilities = float(data.get('current_liabilities'))
    params.interest_expense = float(data.get('interest_expense'))
    params.depreciation = float(data.get('depreciation'))
    
    Asset.query.filter_by(user_id=current_user.id).delete()
    for item in data.get('assets', []):
        if item.get('description'):
            db.session.add(Asset(description=item['description'], amount=float(item.get('amount', 0) or 0), user_id=current_user.id))

    Liability.query.filter_by(user_id=current_user.id).delete()
    for item in data.get('liabilities', []):
        if item.get('description'):
            db.session.add(Liability(description=item['description'], amount=float(item.get('amount', 0) or 0), user_id=current_user.id))

    db.session.commit()

    # Re-fetch and recalculate
    products = [p.to_dict() for p in current_user.products]
    annual_op_ex = float(data.get('annual_operating_expenses'))
    params.annual_operating_expenses = annual_op_ex
    db.session.commit()

    forecast = calculate_profitability(
        products=products, cogs_percentage=params.cogs_percentage,
        annual_operating_expenses=annual_op_ex, tax_rate=params.tax_rate,
        seasonality_factors=json.loads(params.seasonality)
    )
    
    # ... (ratio calculations and forecast updates) ...

    return jsonify(forecast)

@bp.route("/loan-calculator", methods=['GET', 'POST'])
@login_required
def loan_calculator():
    params = current_user.financial_params
    if not params:
        return redirect(url_for('main.financial_forecast'))

    quarterly_net_profit = params.quarterly_net_profit or 0
    monthly_net_profit = quarterly_net_profit / 3
    net_operating_income = params.net_operating_income or 0

    assessment, dscr, dscr_status, schedule, monthly_payment = None, 0.0, "", None, None
    form_data = {
        'loan_amount': params.loan_amount,
        'interest_rate': params.loan_interest_rate,
        'loan_term': params.loan_term
    }

    if request.method == 'POST':
        loan_amount = float(request.form.get('loan_amount', '0').replace(',', '') or 0)
        interest_rate = float(request.form.get('interest_rate', 0))
        loan_term = int(request.form.get('loan_term', 0))
        
        form_data = {'loan_amount': loan_amount, 'interest_rate': interest_rate, 'loan_term': loan_term}
        loan_data = calculate_loan_schedule(loan_amount, interest_rate, loan_term)
        monthly_payment = loan_data.get("monthly_payment")
        schedule = loan_data.get("schedule")

        # Persist to DB instead of session
        params.loan_amount = loan_amount
        params.loan_interest_rate = interest_rate
        params.loan_term = loan_term
        params.loan_monthly_payment = monthly_payment
        params.loan_schedule = json.dumps(schedule)
        db.session.commit()

    # This block runs for both POST and GET with session data
    if params.loan_monthly_payment:
        monthly_payment = params.loan_monthly_payment
        if params.loan_schedule:
            schedule = json.loads(params.loan_schedule)
        if monthly_payment and monthly_payment > 0:
            total_debt_service = monthly_payment * 12
            dscr = calculate_dscr(net_operating_income, total_debt_service)

            if dscr < 1.0:
                assessment = g.assessment_messages.get('high_risk')
            elif dscr < 1.25:
                assessment = g.assessment_messages.get('medium_risk')
            else:
                assessment = g.assessment_messages.get('low_risk')

            if assessment:
                dscr_status = assessment.get('dscr_status', '')

    return render_template('loan-calculator.html', 
                           quarterly_net_profit=quarterly_net_profit,
                           monthly_payment=monthly_payment,
                           form_data=form_data,
                           assessment=assessment,
                           dscr=dscr,
                           dscr_status=dscr_status,
                           schedule=schedule)

@bp.route("/export-forecast")
@login_required
def export_forecast():
    params = current_user.financial_params
    products = [p.to_dict() for p in current_user.products]
    operating_expenses = [e.to_dict() for e in current_user.expenses]
    loan_details = {
        'loan_amount': params.loan_amount,
        'interest_rate': params.loan_interest_rate,
        'loan_term': params.loan_term,
        'monthly_payment': params.loan_monthly_payment,
        'schedule': json.loads(params.loan_schedule) if params.loan_schedule else None,
    }

    spreadsheet_file = create_forecast_spreadsheet(
        products, operating_expenses, params.cogs_percentage, loan_details,
        json.loads(params.seasonality), params.company_name,
        params.depreciation, params.interest_expense
    )

    return send_file(
        spreadsheet_file,
        as_attachment=True,
        download_name='financial_forecast.xlsx',
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )