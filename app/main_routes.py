import json
from flask import Blueprint, render_template, request, jsonify, send_file, redirect, url_for, flash, g, current_app
from typing import Any, Dict
from sqlalchemy import update, delete
from flask_login import login_required, current_user

from .extensions import db
from .models import FinancialParams, Asset, Liability, BusinessStartupActivity
from logic.loan import calculate_loan_schedule
from logic.financial_ratios import calculate_dscr
from utils.export import create_forecast_spreadsheet
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
            db.session.rollback() # Rollback the session to prevent further errors
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
        form_ids = request.form.getlist('id')
        form_activities = request.form.getlist('activity')
        form_descriptions = request.form.getlist('description')
        form_weights = request.form.getlist('weight')
        form_progresses = request.form.getlist('progress')

        total_weight = sum(int(w) for w in form_weights if w.isdigit())
        if total_weight > 100:
            flash(f'Total weight cannot exceed 100%. Current: {total_weight}%.', 'danger')
            # Re-render with submitted data to avoid losing user input
            activities_for_template = []
            for i in range(len(form_activities)):
                activities_for_template.append({
                    'id': form_ids[i], 'activity': form_activities[i], 'description': form_descriptions[i],
                    'weight': form_weights[i], 'progress': form_progresses[i]
                })
            return render_template('startup_activities.html', activities=activities_for_template, total_weight=total_weight), 400

        existing_activities = {str(act.id): act for act in BusinessStartupActivity.query.filter_by(user_id=current_user.id).all()}
        submitted_ids = set()

        for i in range(len(form_activities)):
            activity_id = form_ids[i]
            activity_data = {
                'activity': form_activities[i].strip(), 'description': form_descriptions[i].strip(),
                'weight': int(form_weights[i]), 'progress': int(form_progresses[i]), 'user_id': current_user.id
            }
            if activity_id in existing_activities:
                # Use the sqlalchemy.update() construct for better type compatibility
                stmt = update(BusinessStartupActivity).where(BusinessStartupActivity.id == activity_id).values(**activity_data)
                db.session.execute(stmt)
                submitted_ids.add(activity_id)
            elif activity_data['activity']: # It's a new row
                db.session.add(BusinessStartupActivity(**activity_data))

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
    from . import services
    products, expenses, company_name = services.get_product_and_expense_data(current_user.id)
    page_data = {
        "products": products,
        "expenses": expenses,
        "company_name": company_name,
        "save_url": url_for('main.save_product_details'),
        "continue_url": url_for('main.financial_forecast')
    }
    return render_template('product-detail.html', page_data=page_data)

@bp.route("/save-product-details", methods=["POST"])
@login_required
def save_product_details():
    from . import services
    data = request.get_json()
    services.save_product_and_expense_data(current_user.id, data)
    return jsonify({'status': 'success'})

@bp.route("/financial-forecast", methods=["GET"])
@login_required
def financial_forecast():
    from . import services
    financial_params = current_user.financial_params
    if not financial_params:
        flash('Financial parameters not found. Please visit Product Detail page first.', 'warning')
        return redirect(url_for('main.product_detail'))

    assets = [a.to_dict() for a in current_user.assets]
    liabilities = [l.to_dict() for l in current_user.liabilities]
    operating_expenses = [e.to_dict() for e in current_user.expenses]
    financial_params.annual_operating_expenses = sum((e['amount'] * 12 if e['frequency'] == 'monthly' else e['amount'] * 4) for e in operating_expenses)

    forecast = services.get_or_recalculate_forecast(current_user)

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
    from . import services
    data = request.get_json()

    db.session.execute(delete(Asset).where(Asset.user_id == current_user.id))
    for item in data.get('assets', []):
        if item.get('description'):
            db.session.add(Asset(description=item['description'], amount=float(item.get('amount', 0) or 0), user_id=current_user.id))

    db.session.execute(delete(Liability).where(Liability.user_id == current_user.id))
    for item in data.get('liabilities', []):
        if item.get('description'):
            db.session.add(Liability(description=item['description'], amount=float(item.get('amount', 0) or 0), user_id=current_user.id))
    
    db.session.commit()

    # Refresh the user object to ensure it has the updated assets and liabilities
    db.session.refresh(current_user)

    forecast = services.get_or_recalculate_forecast(current_user, data)
    return jsonify(forecast)

@bp.route("/loan-calculator", methods=['GET', 'POST'])
@login_required
def loan_calculator():
    from . import services
    params = current_user.financial_params
    if not params:
        return redirect(url_for('main.financial_forecast'))

    # Recalculate forecast to ensure all data is fresh
    forecast = services.get_or_recalculate_forecast(current_user)

    quarterly_net_profit = params.quarterly_net_profit or 0
    annual_net_profit = params.annual_net_profit or 0
    # Use the true monthly net profit if available, otherwise estimate from annual
    monthly_net_profit = annual_net_profit / 12 if annual_net_profit else (quarterly_net_profit / 3)

    net_operating_income = params.net_operating_income or 0
    interest_expense = params.interest_expense or 0
    icr = net_operating_income / interest_expense if interest_expense > 0 else 0
    
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
        return redirect(url_for('main.loan_calculator'))

    # On a GET request, load the saved loan data from the database
    if request.method == 'GET' and params.loan_monthly_payment:
        monthly_payment = params.loan_monthly_payment
        if params.loan_schedule:
            schedule = params.loan_schedule  # Pass the raw JSON string to the template

    # This block runs for both POST and for GET requests that have loaded data
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
                           annual_net_profit=annual_net_profit,
                           monthly_net_profit=monthly_net_profit,
                           monthly_payment=monthly_payment,
                           form_data=form_data,
                           assessment=assessment,
                           dscr=dscr,
                           dscr_status=dscr_status,
                           schedule=schedule,
                           icr=icr)

@bp.route("/export-forecast")
@login_required
def export_forecast():
    params = current_user.financial_params
    products = [p.to_dict() for p in current_user.products]
    operating_expenses = [e.to_dict() for e in current_user.expenses]
    startup_activities = [a.to_dict() for a in current_user.startup_activities]
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
        params.depreciation, params.interest_expense, startup_activities
    )

    return send_file(
        spreadsheet_file,
        as_attachment=True,
        download_name='financial_forecast.xlsx',
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )