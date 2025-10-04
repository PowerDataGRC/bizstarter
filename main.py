import os
import json
from flask import Flask, render_template, request, session, jsonify, send_file, redirect, url_for, flash
from flask_migrate import Migrate
from flask_login import UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from extensions import db, login_manager
import click

app = Flask(__name__)
app.config['SECRET_KEY'] = os.urandom(24)
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# --- Database Configuration ---
# Use DATABASE_URL from environment variables if available, otherwise fallback to SQLite
prod_db_url = os.environ.get('DATABASE_URL') or \
              os.environ.get('POSTGRES_URL')
if prod_db_url:
    # Replace postgres:// with postgresql:// for SQLAlchemy compatibility
    prod_db_url = prod_db_url.replace("postgres://", "postgresql://")
    # Ensure SSL is required for production databases
    if 'sslmode' not in prod_db_url:
        prod_db_url += "?sslmode=require"
    app.config['SQLALCHEMY_DATABASE_URI'] = prod_db_url
    # Add engine options for robust pooling with serverless DBs
    app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
        "pool_pre_ping": True,
        "pool_recycle": 300
    }
    # For remote DBs (like Neon), set connect_timeout and search_path
    if 'localhost' not in prod_db_url:
        app.config['SQLALCHEMY_ENGINE_OPTIONS']['connect_args'] = {
            "connect_timeout": 30
        }
        # Set search_path for providers like Neon.
        # It's better to parse the db name from the URL if possible.
        from sqlalchemy.engine.url import make_url
        db_name = make_url(prod_db_url).database
        if db_name:
            app.config['SQLALCHEMY_ENGINE_OPTIONS']['connect_args']['options'] = f'-c search_path={db_name}'

else:
    # Use absolute path for local SQLite DB to avoid ambiguity
    instance_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'instance')
    os.makedirs(instance_path, exist_ok=True)
    app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{os.path.join(instance_path, "bizstarter.db")}'

from profitability import calculate_profitability
from loan import calculate_loan_schedule
from financial_ratios import calculate_dscr, calculate_key_ratios, calculate_advanced_ratios # Import the new functions
from export import create_forecast_spreadsheet
from database import get_assessment_messages

from models import User, Product, Expense, FinancialParams, Asset, Liability, AssessmentMessage, BusinessStartupActivity

# Initialize extensions
db.init_app(app)
login_manager.init_app(app)
migrate = Migrate(app, db)
login_manager.login_view = 'login'

@app.cli.command("seed-db")
def seed_db_command():
    """Seeds the database with initial data (e.g., assessment messages)."""
    if AssessmentMessage.query.first():
        print("Assessment messages table is not empty. Skipping seed.")
        return

    print("Seeding assessment_messages table...")
    try:
        with open('assessment_messages.json', 'r') as f:
            json_data = json.load(f)
        
        for risk_level, data in json_data.items():
            message = AssessmentMessage(**data, risk_level=risk_level)
            db.session.add(message)
        db.session.commit()
        print("Assessment messages seeded successfully.")
    except FileNotFoundError:
        print("Warning: assessment_messages.json not found. Skipping seed.")
    except Exception as e:
        print(f"Error seeding assessment messages: {e}")
        db.session.rollback()

@app.cli.command("getenv")
@click.argument("variable")
def getenv_command(variable):
    """Prints the value of an environment variable."""
    value = os.environ.get(variable)
    if value:
        click.echo(f"{variable}={value}")
    else:
        click.echo(f"'{variable}' is not set.")


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

@app.before_request
def load_assessment_messages():
    """Load assessment messages from DB into the request context if not already present."""
    from flask import g
    if 'assessment_messages' not in g:
        g.assessment_messages = get_assessment_messages()

@app.route("/")
def index():
    if current_user.is_authenticated:
        return redirect(url_for('intro'))
    return redirect(url_for('login'))

@app.route("/intro")
def intro():
    return render_template('intro.html')

@app.route("/library")
def library():
    return render_template('library.html')

@app.route('/startup-activities', methods=['GET', 'POST'])
@login_required
def startup_activities():
    if request.method == 'POST':
        # Clear existing activities for the current user only
        BusinessStartupActivity.query.filter_by(user_id=current_user.id).delete()

        activities = request.form.getlist('activity')
        descriptions = request.form.getlist('description')
        weights = request.form.getlist('weight')
        progresses = request.form.getlist('progress')

        total_weight = 0
        new_activities = []

        for i in range(len(activities)):
            activity_text = activities[i].strip()
            weight_val = weights[i].strip()
            progress_val = progresses[i].strip()
            if activity_text and weight_val: # Ensure row is not empty
                try:
                    weight = int(weight_val)
                    progress = int(progress_val)
                    total_weight += weight
                    new_activities.append(
                        BusinessStartupActivity(
                            activity=activity_text,
                            description=descriptions[i].strip(),
                            weight=weight,
                            progress=progress,
                            user_id=current_user.id
                        )
                    )
                except ValueError:
                    flash('Invalid weight value entered. Please use numbers only.', 'danger')
                    activities_data = zip(activities, descriptions, weights, progresses)
                    return render_template('startup_activities.html', activities=activities_data, total_weight="Error"), 400

        if total_weight > 100:
            flash(f'Total weight cannot exceed 100%. Current total is {total_weight}%.', 'danger')
            activities_data = zip(activities, descriptions, weights)
            return render_template('startup_activities.html', activities=activities_data, total_weight=total_weight), 400

        # If validation passes, add to session and commit
        db.session.add_all(new_activities)
        db.session.commit()

        flash('Startup activities have been updated successfully!', 'success')

        return redirect(url_for('product_detail'))

    # For GET request, get activities for the current user
    activities = BusinessStartupActivity.query.filter_by(user_id=current_user.id).order_by(BusinessStartupActivity.id).all()

    # If no activities are found for the current user, display a message.
    # Initial activities are seeded during user registration.
    if not activities:
       flash('No startup activities found. You can add them below.', 'info')

    total_weight = sum(act.weight for act in activities)
    return render_template('startup_activities.html', activities=activities, total_weight=total_weight)



@app.route("/product-detail", methods=["GET", "POST"])
@login_required
def product_detail():
    # Load products and expenses from DB for the current user
    products = current_user.products
    expenses = current_user.expenses
    financial_params = current_user.financial_params
 
    # Initial data is now seeded at registration. If data is missing for an older user,
    # they will see an empty state, which is the correct behavior.
    if not expenses:
        flash('No expenses found. Default expenses are added for new users.', 'info')
    if not products:
        flash('No products found. You can add them on this page.', 'info')

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
            price = float(p.get('price', 0) or 0)
            sales_volume = int(p.get('sales_volume', 0) or 0)
            new_product = Product(
                description=p.get('description'),
                price=price,
                sales_volume=sales_volume,
                sales_volume_unit=p.get('sales_volume_unit', 'monthly'),
                user_id=current_user.id
            )
            db.session.add(new_product)
        except (ValueError, TypeError):
            # Skip rows with invalid number formats
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
        # This should not happen for users created after this fix.
        # For older users, redirect them to a page where params can be set up.
        flash('Financial parameters not found. Please visit the Product Detail page first.', 'warning')
        return redirect(url_for('product_detail'))

    assets = current_user.assets
    liabilities = current_user.liabilities

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
        return redirect(url_for('intro'))
    if request.method == 'POST':
        user = User.query.filter_by(username=request.form.get('username')).first()
        if user and check_password_hash(user.password_hash, request.form.get('password')):
            login_user(user, remember=True)
            return redirect(url_for('intro'))
        else:
            flash('Invalid username or password.', 'danger')
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('intro'))
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

        # --- Seed all initial data for the new user in one transaction ---
        initial_activities = [
            {'activity': 'Conduct Market Research', 'description': 'Analyze competitors and demand', 'weight': 10, 'progress': 0},
            {'activity': 'Write a Business Plan', 'description': 'Mission, strategies, financials, goals', 'weight': 12, 'progress': 0},
            {'activity': 'Choose a Business Name', 'description': 'Brand and legal name selection', 'weight': 4, 'progress': 0},
            {'activity': 'Pick Business Structure (LLC, Corp, etc.)', 'description': 'Select legal form and file with state', 'weight': 7, 'progress': 0},
            {'activity': 'Register Entity & Obtain Tax IDs', 'description': 'File paperwork; get EIN', 'weight': 7, 'progress': 0},
            {'activity': 'Obtain Licenses, Permits, Zoning Approvals', 'description': 'Meet all regulatory requirements', 'weight': 8, 'progress': 0},
            {'activity': 'Open Business Bank Account', 'description': 'Financial setup and credit', 'weight': 4, 'progress': 0},
            {'activity': 'Arrange Funding/Cash Flow', 'description': 'Secure startup, operating, or loan funds', 'weight': 8, 'progress': 0},
            {'activity': 'Set Up Accounting & Payroll Systems', 'description': 'Bookkeeping, compliance, employee pay', 'weight': 6, 'progress': 0},
            {'activity': 'Secure Business Insurance', 'description': 'Liability, property, workers’ comp, etc.', 'weight': 5, 'progress': 0},
            {'activity': 'Choose Location, Lease, or Buy', 'description': 'Decide HQ, retail, or office space', 'weight': 6, 'progress': 0},
            {'activity': 'Hire/Train Employees', 'description': 'Recruit, onboard, comply with reporting', 'weight': 6, 'progress': 0},
            {'activity': 'Develop Website, Social Media, Branding', 'description': 'Marketing launch and digital presence', 'weight': 6, 'progress': 0},
            {'activity': 'Purchase Equipment, Furniture, Inventory', 'description': 'Supplies and capital purchases', 'weight': 6, 'progress': 0},
            {'activity': 'Prepare Operational & Privacy Policies', 'description': 'SOPs, data/privacy, contracts, legal docs', 'weight': 5, 'progress': 0}
        ]
        initial_expenses = [
            Expense(item='Rent/Lease', amount=1200.0, frequency='monthly', readonly=True, user_id=new_user.id),
            Expense(item='Utilities', amount=300.0, frequency='monthly', readonly=True, user_id=new_user.id),
            Expense(item='Supplies', amount=150.0, frequency='monthly', readonly=True, user_id=new_user.id),
            Expense(item='Marketing', amount=250.0, frequency='monthly', readonly=True, user_id=new_user.id),
            Expense(item='Insurance', amount=100.0, frequency='monthly', readonly=True, user_id=new_user.id),
            Expense(item='Salaries/Wages', amount=2000.0, frequency='monthly', readonly=True, user_id=new_user.id),
            Expense(item='Legal', amount=100.0, frequency='monthly', readonly=True, user_id=new_user.id),
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

        # Add all initial data to the session
        db.session.add(FinancialParams(user_id=new_user.id))
        db.session.add_all([BusinessStartupActivity(**item, user_id=new_user.id) for item in initial_activities])
        db.session.add_all(initial_expenses)
        db.session.add_all(initial_assets)
        db.session.add_all(initial_liabilities)
        db.session.add_all(initial_products)

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
    from flask import g
    if not params:
        return redirect(url_for('financial_forecast'))

    quarterly_net_profit = params.quarterly_net_profit
    monthly_net_profit = quarterly_net_profit / 3 if quarterly_net_profit is not None else 0
    annual_net_profit = params.annual_net_profit
    total_annual_revenue = params.total_annual_revenue
    annual_operating_expenses = params.annual_operating_expenses
    net_operating_income = params.net_operating_income

    monthly_payment = None
    assessment = None
    dscr = 0.0
    dscr_status = ""
    schedule = None

    # Load existing loan details from session to persist form data and results
    loan_details = session.get('loan_details', {})
    form_data = {
        'loan_amount': loan_details.get('loan_amount'),
        'interest_rate': loan_details.get('interest_rate'),
        'loan_term': loan_details.get('loan_term')
    }

    if request.method == 'POST' and quarterly_net_profit is not None:
        loan_amount_str = request.form.get('loan_amount', '0').replace(',', '')
        loan_amount = float(loan_amount_str or 0)
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
            'schedule': schedule
        }

        if monthly_payment is not None and monthly_payment > 0:
            # DSCR = Net Operating Income / Total Debt Service
            total_debt_service = monthly_payment * 12

            dscr = calculate_dscr(net_operating_income, total_debt_service)

            if dscr < 1.0:
                dscr_status = g.assessment_messages.get('high_risk', {}).get('dscr_status', '')
            elif dscr < 1.25:
                dscr_status = g.assessment_messages.get('medium_risk', {}).get('dscr_status', '')
            else:
                dscr_status = g.assessment_messages.get('low_risk', {}).get('dscr_status', '')

            if monthly_net_profit < monthly_payment * 1.5:
                assessment = g.assessment_messages.get('medium_risk')
            elif monthly_net_profit < monthly_payment:
                 assessment = g.assessment_messages.get('high_risk')
            else:
                assessment = g.assessment_messages.get('low_risk')
    elif loan_details: # This is a GET request with existing data in session
        monthly_payment = loan_details.get('monthly_payment')
        schedule = loan_details.get('schedule')

        if monthly_payment is not None and monthly_payment > 0 and net_operating_income is not None:
            total_debt_service = monthly_payment * 12
            dscr = calculate_dscr(net_operating_income, total_debt_service)

            if dscr < 1.0:
                dscr_status = g.assessment_messages.get('high_risk', {}).get('dscr_status', '')
            elif dscr < 1.25:
                dscr_status = g.assessment_messages.get('medium_risk', {}).get('dscr_status', '')
            else:
                dscr_status = g.assessment_messages.get('low_risk', {}).get('dscr_status', '')

        if monthly_payment is not None and monthly_net_profit is not None:
            if monthly_net_profit < monthly_payment * 1.5:
                assessment = g.assessment_messages.get('medium_risk')
            elif monthly_net_profit < monthly_payment:
                 assessment = g.assessment_messages.get('high_risk')
            else:
                assessment = g.assessment_messages.get('low_risk')



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

if __name__ == '__main__':
    with app.app_context():
        # This block is for running the local development server.
        # Database management is handled by `flask db` commands.
        # Initial data seeding is handled by `flask seed-db` command.
        pass
    app.run(debug=True)
