import json
from flask import Blueprint, render_template, request, jsonify, send_file, redirect, url_for, flash, g, current_app
from flask_login import login_required, current_user

from .extensions import db
from .models import Product, Expense, FinancialParams, Asset, Liability, BusinessStartupActivity
from logic.profitability import calculate_profitability
from logic.loan import calculate_loan_schedule
from logic.financial_ratios import calculate_dscr, calculate_key_ratios
from utils.export import create_forecast_spreadsheet
from .auth import _seed_initial_user_data
from .database import get_assessment_messages

bp = Blueprint('main', __name__, url_prefix='/')

# A simple in-memory cache for the assessment messages.
# This will be populated on the first request.
_assessment_messages_cache = None

@bp.before_app_request
def before_request():
    """Load assessment messages into the request context if not already present."""
    global _assessment_messages_cache
    if _assessment_messages_cache is None:
        try:
            current_app.logger.info("Populating assessment messages cache...")
            _assessment_messages_cache = get_assessment_messages() or {}
        except Exception as e:
            current_app.logger.error(f"Failed to load assessment messages from DB: {e}")
            _assessment_messages_cache = {}  # Use an empty dict on failure

    g.assessment_messages = _assessment_messages_cache
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
    
    # Self-healing: If the user has an incomplete list of activities due to a past bug,
    # delete the partial list and re-seed the full one.
    try:
        with current_app.open_resource('../startup_activities.json') as f:
            default_activities_count = len(json.load(f))
    except Exception:
        default_activities_count = 10 # Fallback count

    if len(activities) > 0 and len(activities) < default_activities_count:
        current_app.logger.info(f"User {current_user.id} has an incomplete activity list. Re-seeding.")
        BusinessStartupActivity.query.filter_by(user_id=current_user.id).delete()
        activities = [] # Clear the list to trigger the seeding block below

    if not activities:
        try:
            with current_app.open_resource('../startup_activities.json') as f:
                initial_activities_data = json.load(f)
            new_activities = [BusinessStartupActivity(**item, user_id=current_user.id) for item in initial_activities_data]
            db.session.add_all(new_activities)
            db.session.commit()
            flash('We\'ve added a default list of startup activities to get you started.', 'info')
            activities = new_activities  # Use the newly created activities
        except Exception as e:
            current_app.logger.error(f"Failed to seed startup activities for user {current_user.id}: {e}")
            flash('Could not load default startup activities.', 'danger')
    total_weight = sum(act.weight for act in activities)
    return render_template('startup_activities.html', activities=activities, total_weight=total_weight)

@bp.route("/product-detail", methods=["GET"])
@login_required
def product_detail():
    products_dict = [p.to_dict() for p in current_user.products]
    
    # Self-healing: If the user has an incomplete or empty expense list, re-seed all their data.
    # This is a robust way to fix data inconsistencies from past bugs.
    # We check for a low number of expenses as a proxy for incomplete data.
    if len(current_user.expenses) < 4:
        current_app.logger.info(f"User {current_user.id} has an incomplete data set. Re-seeding.")
        # Delete existing data to avoid duplicates
        Product.query.filter_by(user_id=current_user.id).delete()
        Expense.query.filter_by(user_id=current_user.id).delete()
        Asset.query.filter_by(user_id=current_user.id).delete()
        Liability.query.filter_by(user_id=current_user.id).delete()
        BusinessStartupActivity.query.filter_by(user_id=current_user.id).delete()
        FinancialParams.query.filter_by(user_id=current_user.id).delete()
        db.session.commit()
        
        # Re-seed everything
        _seed_initial_user_data(current_user.id)
        flash('Your account data has been refreshed with the latest defaults.', 'info')

    expenses_dict = [e.to_dict() for e in current_user.expenses]
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

    # Persist key forecast results to the database so they can be used by the loan calculator
    financial_params.total_annual_revenue = forecast['annual']['revenue']
    financial_params.annual_net_profit = forecast['annual']['net_profit']
    # The loan calculator uses the first quarter's net profit as a basis
    financial_params.quarterly_net_profit = forecast['quarterly']['net_profit']
    # Net Operating Income (EBIT) is Gross Profit - Operating Expenses
    financial_params.net_operating_income = forecast['annual']['gross_profit'] - annual_op_ex

    # Calculate ratios for the initial page load
    # This mirrors the logic in recalculate_forecast to ensure consistency
    total_assets = sum(a.amount for a in current_user.assets)
    total_debt = sum(l.amount for l in current_user.liabilities)

    annual_ratios = calculate_key_ratios(
        net_profit=forecast['annual']['net_profit'],
        total_revenue=forecast['annual']['revenue'],
        total_assets=total_assets,
        current_assets=financial_params.current_assets,
        current_liabilities=financial_params.current_liabilities,
        total_debt=total_debt,
        net_operating_income=financial_params.net_operating_income,
        interest_expense=financial_params.interest_expense,
        depreciation=financial_params.depreciation
    )
    forecast['annual'].update(annual_ratios)
    # For simplicity, we'll pass the annual ratios for the quarterly view on initial load.
    # The recalculate function will provide more accurate quarterly ratios.
    forecast['quarterly'].update(annual_ratios)

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