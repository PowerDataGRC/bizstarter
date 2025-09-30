import os
import json
from flask import Flask, render_template, request, session, jsonify, send_file, redirect, url_for, flash
from flask_login import UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from extensions import db, login_manager
from profitability import calculate_profitability
from loan import calculate_loan_schedule
from financial_ratios import calculate_dscr, calculate_key_ratios, calculate_advanced_ratios # Import the new functions
from export import create_forecast_spreadsheet
from database import init_db, get_assessment_messages

app = Flask(__name__)
app.config['SECRET_KEY'] = os.urandom(24)
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# --- Database Configuration ---
# Use Vercel Postgres URL if available (in production), otherwise use local SQLite
if os.environ.get('POSTGRES_URL'):
    app.config['SQLALCHEMY_DATABASE_URI'] = os.environ['POSTGRES_URL'].replace("postgres://", "postgresql://")
else:
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///bizstarter.db'

from models import User, Product, Expense, FinancialParams, Asset, Liability

# Initialize extensions
db.init_app(app)
login_manager.init_app(app)
login_manager.login_view = 'login'

# Define ASSESSMENT_MESSAGES globally, it will be populated during app startup
ASSESSMENT_MESSAGES = {}

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

@app.route("/")
def index():
    if current_user.is_authenticated:
        return redirect(url_for('product_detail'))
    return redirect(url_for('login'))

@app.route("/library")
def library():
    return render_template('library.html')

@app.route("/product-detail", methods=["GET", "POST"])
@login_required
def product_detail():
    # Load products and expenses from DB for the current user
    products = current_user.products
    expenses = current_user.expenses
    financial_params = current_user.financial_params

    # If no expenses in DB for this user, populate with defaults
    if not expenses:
        expenses = [
            Expense(item='Rent/Lease', amount=1200.0, frequency='monthly', readonly=True, user_id=current_user.id),
            Expense(item='Utilities', amount=300.0, frequency='monthly', readonly=True, user_id=current_user.id),
            Expense(item='Supplies', amount=150.0, frequency='monthly', readonly=True, user_id=current_user.id),
            Expense(item='Marketing', amount=250.0, frequency='monthly', readonly=True, user_id=current_user.id),
            Expense(item='Insurance', amount=100.0, frequency='monthly', readonly=True, user_id=current_user.id),
            Expense(item='Salaries/Wages', amount=2000.0, frequency='monthly', readonly=True, user_id=current_user.id),
            Expense(item='Legal', amount=100.0, frequency='monthly', readonly=True, user_id=current_user.id),
        ]
        db.session.add_all(expenses)
        db.session.commit()
    
    # If no products in DB, provide 4 empty ones for initial display
    if not products:
        products = [Product(description='', price=0.0, sales_volume=0, sales_volume_unit='monthly', user_id=current_user.id) for _ in range(4)]
        db.session.add_all(products)
        db.session.commit()

    # Convert DB objects to dictionaries for JSON serialization
    products_dict = [p.to_dict() for p in products]
    expenses_dict = [e.to_dict() for e in expenses]
    company_name = financial_params.company_name if financial_params else ''

    return render_template('product-detail.html', products=products_dict, expenses=expenses_dict, company_name=company_name)

@app.route("/save-product-details", methods=["POST"])
@login_required
def save_product_details():
    data = request.get_json()
    
    # Clear existing products and expenses for the user
    Product.query.filter_by(user_id=current_user.id).delete()
    Expense.query.filter_by(user_id=current_user.id).delete()

    # Add new products from the form
    for p in data.get('products', []):
        try:
            new_product = Product(
                description=p.get('description'),
                price=float(p.get('price', 0) or 0),
                sales_volume=int(p.get('sales_volume', 0) or 0),
                sales_volume_unit=p.get('sales_volume_unit', 'monthly'),
                user_id=current_user.id
            )
            db.session.add(new_product)
        except (ValueError, TypeError):
            continue

    # Add new expenses from the form
    for e in data.get('expenses', []):
        try:
            new_expense = Expense(
                item=e.get('item'),
                amount=float(e.get('amount', 0) or 0),
                frequency=e.get('frequency', 'monthly'),
                readonly=e.get('readonly', False),
                user_id=current_user.id
            )
            db.session.add(new_expense)
        except (ValueError, TypeError):
            continue

    # Update company name
    financial_params = current_user.financial_params
    if not financial_params:
        financial_params = FinancialParams(user_id=current_user.id)
        db.session.add(financial_params)
    financial_params.company_name = data.get('company_name', '')

    db.session.commit()
    return jsonify({'status': 'success'})


@app.route("/financial-forecast", methods=["GET", "POST"])
@login_required
def financial_forecast():
    products = [p.to_dict() for p in current_user.products]
    operating_expenses = [e.to_dict() for e in current_user.expenses]
    
    financial_params = current_user.financial_params
    if not financial_params:
        financial_params = FinancialParams(user_id=current_user.id)
        db.session.add(financial_params)
        db.session.commit()

    assets = current_user.assets
    if not assets:
        assets = [
            Asset(description='Cash & Equivalents', amount=10000.0, user_id=current_user.id),
            Asset(description='Inventory', amount=5000.0, user_id=current_user.id),
            Asset(description='Equipment', amount=35000.0, user_id=current_user.id)
        ]
        db.session.add_all(assets)
        db.session.commit()

    liabilities = current_user.liabilities
    if not liabilities:
        liabilities = [
            Liability(description='Credit Card Debt', amount=5000.0, user_id=current_user.id),
            Liability(description='Bank Loan', amount=20000.0, user_id=current_user.id)
        ]
        db.session.add_all(liabilities)
        db.session.commit()

    assets_dict = [a.to_dict() for a in assets]
    liabilities_dict = [l.to_dict() for l in liabilities]

    total_assets = sum(item.amount for item in assets)
    total_debt = sum(item.amount for item in liabilities)

    # Get params from DB
    cogs_percentage = financial_params.cogs_percentage
    tax_rate = financial_params.tax_rate
    seasonality = json.loads(financial_params.seasonality)
    current_assets = financial_params.current_assets
    current_liabilities = financial_params.current_liabilities
    interest_expense = financial_params.interest_expense
    depreciation = financial_params.depreciation

    if not isinstance(seasonality, list) or len(seasonality) != 12:
        seasonality = [1.0] * 12

    annual_operating_expenses_value = 0
    if operating_expenses:
        for expense in operating_expenses:
            try:
                amount = float(expense.get('amount', 0))
                if expense.get('frequency') == 'monthly':
                    annual_operating_expenses_value += amount * 12
                elif expense.get('frequency') == 'quarterly':
                    annual_operating_expenses_value += amount * 4
            except (ValueError, TypeError):
                continue
    
    forecast = None
    if products:
        forecast = calculate_profitability(
            products=products, 
            cogs_percentage=cogs_percentage, 
            annual_operating_expenses=annual_operating_expenses_value,
            tax_rate=tax_rate,
            seasonality_factors=seasonality
        )
        annual_net_profit = forecast.get('annual', {}).get('net_profit', 0)
        annual_revenue = forecast.get('annual', {}).get('revenue', 0)
        quarterly_net_profit = forecast.get('quarterly', {}).get('net_profit', 0)
        quarterly_revenue = forecast.get('quarterly', {}).get('revenue', 0)

        # Calculate Net Operating Income (Gross Profit - Operating Expenses)
        annual_gross_profit = forecast.get('annual', {}).get('gross_profit', 0)
        net_operating_income = annual_gross_profit - annual_operating_expenses_value

        # Update forecast with basic ratios
        forecast['annual'].update(calculate_key_ratios(annual_net_profit, annual_revenue, total_assets))
        forecast['quarterly'].update(calculate_key_ratios(quarterly_net_profit, quarterly_revenue, total_assets))

        # Calculate and add advanced ratios
        ebitda = net_operating_income + depreciation
        operating_cash_flow = annual_net_profit + depreciation
        advanced_ratios = calculate_advanced_ratios(current_assets, current_liabilities, total_debt, total_assets, ebitda, interest_expense, operating_cash_flow)
        forecast['annual'].update(advanced_ratios)

        # For quarterly, we'll scale down the annual inputs for a rough estimate
        annual_tax = forecast.get('annual', {}).get('tax', 0)
        quarterly_ebitda = quarterly_net_profit + (annual_tax / 4) + (interest_expense / 4)
        quarterly_ocf = quarterly_net_profit + (depreciation / 4)
        # Note: Using total assets/liabilities for quarterly ratios is a simplification
        quarterly_advanced_ratios = calculate_advanced_ratios(current_assets, current_liabilities, total_debt, total_assets, quarterly_ebitda, interest_expense / 4, quarterly_ocf)
        forecast['quarterly'].update(quarterly_advanced_ratios)

        # Store key results in financial_params for loan calculator
        financial_params.quarterly_net_profit = quarterly_net_profit
        financial_params.annual_net_profit = annual_net_profit
        financial_params.total_annual_revenue = annual_revenue
        financial_params.net_operating_income = net_operating_income
        financial_params.annual_operating_expenses = annual_operating_expenses_value
        db.session.commit()

    return render_template('financial-forecast.html', 
                             products=products, 
                             forecast=forecast, 
                             cogs_percentage=cogs_percentage,
                             operating_expenses=operating_expenses,
                             annual_operating_expenses=annual_operating_expenses_value,
                             tax_rate=tax_rate,
                             seasonality=seasonality,
                             assets=assets_dict,
                             liabilities=liabilities_dict,
                             total_assets=total_assets,
                             current_assets=current_assets,
                             current_liabilities=current_liabilities,
                             total_debt=total_debt,
                             interest_expense=interest_expense,
                             depreciation=depreciation
                             )

@app.route("/recalculate-forecast", methods=["POST"])
@login_required
def recalculate_forecast():
    data = request.get_json()

    # Update FinancialParams
    params = current_user.financial_params
    params.cogs_percentage = float(data.get('cogs_percentage'))
    params.tax_rate = float(data.get('tax_rate'))
    params.seasonality = json.dumps([float(v) for v in data.get('seasonality', [1.0] * 12)])
    params.current_assets = float(data.get('current_assets'))
    params.current_liabilities = float(data.get('current_liabilities'))
    params.interest_expense = float(data.get('interest_expense'))
    params.depreciation = float(data.get('depreciation'))
    
    # Update Assets
    Asset.query.filter_by(user_id=current_user.id).delete()
    for item in data.get('assets', []):
        if item.get('description'):
            db.session.add(Asset(description=item['description'], amount=float(item.get('amount', 0) or 0), user_id=current_user.id))

    # Update Liabilities
    Liability.query.filter_by(user_id=current_user.id).delete()
    for item in data.get('liabilities', []):
        if item.get('description'):
            db.session.add(Liability(description=item['description'], amount=float(item.get('amount', 0) or 0), user_id=current_user.id))

    db.session.commit()

    # Re-fetch data for calculation
    cogs_percentage = params.cogs_percentage
    annual_operating_expenses_value = float(data.get('annual_operating_expenses')) # This is calculated on the fly, not stored
    tax_rate = params.tax_rate
    seasonality = json.loads(params.seasonality)
    total_assets = sum(a.amount for a in current_user.assets)
    total_debt = sum(l.amount for l in current_user.liabilities)
    current_assets = params.current_assets
    current_liabilities = params.current_liabilities
    interest_expense = params.interest_expense
    depreciation = params.depreciation
    products = [p.to_dict() for p in current_user.products]

    # Store calculated expenses for other parts of the app
    params.annual_operating_expenses = annual_operating_expenses_value
    db.session.commit()

    if not products:
        return jsonify({'error': 'No product data in session'}), 400

    forecast = calculate_profitability(
        products=products, 
        cogs_percentage=cogs_percentage, 
        annual_operating_expenses=annual_operating_expenses_value,
        tax_rate=tax_rate,
        seasonality_factors=seasonality
    )

    # Refactored: Calculate ratios and add them to the forecast dictionary
    annual_net_profit = forecast.get('annual', {}).get('net_profit', 0)
    annual_revenue = forecast.get('annual', {}).get('revenue', 0)
    quarterly_net_profit = forecast.get('quarterly', {}).get('net_profit', 0)
    quarterly_revenue = forecast.get('quarterly', {}).get('revenue', 0)

    # Calculate Net Operating Income (Gross Profit - Operating Expenses)
    annual_gross_profit = forecast.get('annual', {}).get('gross_profit', 0)
    net_operating_income = annual_gross_profit - annual_operating_expenses_value

    # Update forecast with basic ratios
    forecast['annual'].update(calculate_key_ratios(annual_net_profit, annual_revenue, total_assets))
    forecast['quarterly'].update(calculate_key_ratios(quarterly_net_profit, quarterly_revenue, total_assets))
    
    # Calculate and add advanced ratios
    ebitda = net_operating_income + depreciation
    operating_cash_flow = annual_net_profit + depreciation
    advanced_ratios = calculate_advanced_ratios(current_assets, current_liabilities, total_debt, total_assets, ebitda, interest_expense, operating_cash_flow)
    forecast['annual'].update(advanced_ratios)

    # For quarterly, we'll scale down the annual inputs for a rough estimate
    annual_tax = forecast.get('annual', {}).get('tax', 0)
    quarterly_ebitda = quarterly_net_profit + (annual_tax / 4) + (interest_expense / 4)
    quarterly_ocf = quarterly_net_profit + (depreciation / 4)
    # Note: Using total assets/liabilities for quarterly ratios is a simplification
    quarterly_advanced_ratios = calculate_advanced_ratios(current_assets, current_liabilities, total_debt, total_assets, quarterly_ebitda, interest_expense / 4, quarterly_ocf)
    forecast['quarterly'].update(quarterly_advanced_ratios)

    # Update params for loan calculator
    params.quarterly_net_profit = quarterly_net_profit
    params.annual_net_profit = annual_net_profit
    params.total_annual_revenue = annual_revenue
    params.net_operating_income = net_operating_income
    db.session.commit()

    return jsonify(forecast)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('product_detail'))
    if request.method == 'POST':
        user = User.query.filter_by(username=request.form.get('username')).first()
        if user and check_password_hash(user.password_hash, request.form.get('password')):
            login_user(user, remember=True)
            return redirect(url_for('product_detail'))
        else:
            flash('Invalid username or password.', 'danger')
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('product_detail'))
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        if not username or not password:
            flash('Username and password are required.')
            return render_template('register.html')

        existing_user = User.query.filter_by(username=username).first()
        if existing_user:
            flash('Username already exists. Please choose a different one.')
            return render_template('register.html')

        new_user = User(
            username=username,
            password_hash=generate_password_hash(password, method='pbkdf2:sha256')
        )
        db.session.add(new_user)
        db.session.commit()

        # Create an initial FinancialParams for the new user
        new_params = FinancialParams(user_id=new_user.id)
        db.session.add(new_params)
        db.session.commit()

        flash('Registration successful! Please log in.')
        return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))

@app.route("/loan-calculator", methods=['GET', 'POST'])
@login_required
def loan_calculator():
    params = current_user.financial_params
    if not params:
        return redirect(url_for('financial_forecast'))

    quarterly_net_profit = params.quarterly_net_profit
    monthly_net_profit = quarterly_net_profit / 3 if quarterly_net_profit is not None else 0
    annual_net_profit = params.annual_net_profit
    total_annual_revenue = params.total_annual_revenue
    annual_operating_expenses = params.annual_operating_expenses
    net_operating_income = params.net_operating_income

    monthly_payment = None
    schedule = None
    # Load existing loan details from session to persist form data
    form_data = session.get('loan_details', {})
    assessment = None
    dscr = 0.0
    dscr_status = ""

    if request.method == 'POST' and quarterly_net_profit is not None:
        loan_amount = float(request.form.get('loan_amount', 0))
        interest_rate = float(request.form.get('interest_rate', 0))
        loan_term = int(request.form.get('loan_term', 0))
        
        form_data = {
            'loan_amount': loan_amount,
            'interest_rate': interest_rate,
            'loan_term': loan_term
        }

        loan_data = calculate_loan_schedule(loan_amount, interest_rate, loan_term)
        monthly_payment = loan_data.get("monthly_payment")
        schedule = loan_data.get("schedule")
        
        # Save loan details to session for export
        session['loan_details'] = {
            **form_data,
            'monthly_payment': monthly_payment,
            # 'schedule' can be large, so we might not want to store it if not necessary for re-display
        }

        if monthly_payment is not None and monthly_payment > 0:
            # DSCR = Net Operating Income / Total Debt Service
            total_debt_service = monthly_payment * 12

            dscr = calculate_dscr(net_operating_income, total_debt_service)

            if dscr < 1.0:
                dscr_status = ASSESSMENT_MESSAGES.get('high_risk', {}).get('dscr_status', '')
            elif dscr < 1.25:
                dscr_status = ASSESSMENT_MESSAGES.get('medium_risk', {}).get('dscr_status', '')
            else:
                dscr_status = ASSESSMENT_MESSAGES.get('low_risk', {}).get('dscr_status', '')

            if monthly_net_profit < monthly_payment * 1.5:
                assessment = ASSESSMENT_MESSAGES['medium_risk']
            elif monthly_net_profit < monthly_payment:
                 assessment = ASSESSMENT_MESSAGES['high_risk']
            else:
                assessment = ASSESSMENT_MESSAGES['low_risk']

    return render_template('loan-calculator.html', 
                           quarterly_net_profit=quarterly_net_profit,
                           monthly_payment=monthly_payment,
                           form_data=form_data,
                           assessment=assessment,
                           dscr=dscr,
                           dscr_status=dscr_status,
                           schedule=schedule)

@app.route("/export-forecast")
@login_required
def export_forecast():
    # Gather all necessary data from the DB
    products = [p.to_dict() for p in current_user.products]
    operating_expenses = [e.to_dict() for e in current_user.expenses]
    cogs_percentage = current_user.financial_params.cogs_percentage
    company_name = current_user.financial_params.company_name
    depreciation = current_user.financial_params.depreciation
    interest_expense = current_user.financial_params.interest_expense
    seasonality_factors = json.loads(current_user.financial_params.seasonality)
    loan_details = session.get('loan_details', {})

    # Generate the spreadsheet file in memory
    spreadsheet_file = create_forecast_spreadsheet(
        products, operating_expenses, cogs_percentage, loan_details, seasonality_factors, company_name, depreciation, interest_expense
    )

    return send_file(
        spreadsheet_file,
        as_attachment=True,
        download_name='financial_forecast.xlsx',
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )

def vercel_build():
    """Function to be called by Vercel during the build process."""
    with app.app_context():
        # This is safe for Vercel's ephemeral filesystem
        db.create_all()
        init_db(app)
        # Also load messages during Vercel build
        global ASSESSMENT_MESSAGES
        ASSESSMENT_MESSAGES = get_assessment_messages()

if __name__ == '__main__':
    with app.app_context():
        # For local development, check if a migration is needed
        from sqlalchemy import inspect
        inspector = inspect(db.engine)
        if not inspector.has_table('financial_params') or 'net_operating_income' not in [c['name'] for c in inspector.get_columns('financial_params')]:
            print("Database schema is outdated or does not exist. Recreating database...")
            # This is a destructive action, suitable for local dev.
            # It will delete all existing data.
            db.drop_all()
            db.create_all()
            init_db(app)
            print("Database recreated successfully.")
        
        # Load messages for local development
        ASSESSMENT_MESSAGES = get_assessment_messages()
        if not ASSESSMENT_MESSAGES:
            print("Warning: ASSESSMENT_MESSAGES dictionary is empty. Seeding database...")
            init_db(app) # Seed the DB if it's empty
            ASSESSMENT_MESSAGES = get_assessment_messages()

    app.run(debug=True)
