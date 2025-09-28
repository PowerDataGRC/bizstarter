import os
import json
from flask import Flask, render_template, request, session, jsonify, send_file
from profitability import calculate_profitability
from loan import calculate_loan_schedule
from financial_ratios import calculate_dscr, calculate_key_ratios, calculate_advanced_ratios # Import the new functions
from export import create_forecast_spreadsheet

app = Flask(__name__)
app.secret_key = os.urandom(24)

# Load assessment messages from JSON file
with open('assessment_messages.json') as f:
    ASSESSMENT_MESSAGES = json.load(f)

@app.route("/")
def index():
    return render_template('intro.html')

@app.route("/library")
def library():
    return render_template('library.html')

@app.route("/product-detail", methods=["GET", "POST"])
def product_detail():
    if request.args.get('startover'):
        session.clear()

    # Load products and expenses from session or provide defaults
    products = session.get('products', [])
    expenses = session.get('expenses', [])

    # If no expenses in session, populate with defaults
    if not expenses:
        expenses = [
            {'item': 'Rent/Lease', 'amount': 1200.0, 'frequency': 'monthly', 'readonly': True},
            {'item': 'Utilities', 'amount': 300.0, 'frequency': 'monthly', 'readonly': True},
            {'item': 'Supplies', 'amount': 150.0, 'frequency': 'monthly', 'readonly': True},
            {'item': 'Marketing', 'amount': 250.0, 'frequency': 'monthly', 'readonly': True},
            {'item': 'Insurance', 'amount': 100.0, 'frequency': 'monthly', 'readonly': True},
            {'item': 'Salaries/Wages', 'amount': 2000.0, 'frequency': 'monthly', 'readonly': True},
            {'item': 'Legal', 'amount': 100.0, 'frequency': 'monthly', 'readonly': True},
        ]
        session['expenses'] = expenses
    
    # If no products in session, populate with 4 empty ones for initial display
    # Ensure numeric fields are initialized as actual numbers (0.0) for consistency
    if not products and request.method == "GET": # Only for initial GET request
        products = [{'description': '', 'price': 0.0, 'sales_volume': 0, 'sales_volume_unit': 'monthly'} for _ in range(4)]
        session['products'] = products # Save initial empty products to session

    return render_template('product-detail.html', products=products, expenses=expenses)

@app.route("/save-product-details", methods=["POST"])
def save_product_details():
    data = request.get_json()
    
    # Process products data to convert numeric fields
    processed_products = []
    for p in data.get('products', []):
        try:
            p['price'] = float(p.get('price', 0) or 0) # Convert to float, default to 0
            p['sales_volume'] = int(p.get('sales_volume', 0) or 0) # Convert to int, default to 0
            processed_products.append(p)
        except (ValueError, TypeError):
            # Handle cases where conversion fails, perhaps log or skip invalid entries
            continue 

    # Process expenses data to convert numeric fields
    processed_expenses = []
    for e in data.get('expenses', []):
        try:
            e['amount'] = float(e.get('amount', 0) or 0) # Convert to float, default to 0
            processed_expenses.append(e)
        except (ValueError, TypeError):
            # Handle cases where conversion fails
            continue

    session['products'] = processed_products
    session['expenses'] = processed_expenses
    session['company_name'] = data.get('company_name', '') # Save company name
    return jsonify({'status': 'success'})


@app.route("/financial-forecast", methods=["GET", "POST"])
def financial_forecast():
    products = session.get('products', [])
    cogs_percentage = session.get('cogs_percentage', 35.0)
    operating_expenses = session.get('expenses', []) # Use 'expenses' from session
    # New: Get tax and seasonality from session or set defaults
    tax_rate = session.get('tax_rate', 8.0)
    seasonality = session.get('seasonality', [1.0] * 12)
    total_assets = session.get('total_assets', 50000.0) # New: Total Assets
    # New ratio inputs
    current_assets = session.get('current_assets', 15000.0)
    current_liabilities = session.get('current_liabilities', 8000.0)
    total_debt = session.get('total_debt', 25000.0)
    interest_expense = session.get('interest_expense', 2000.0)
    depreciation = session.get('depreciation', 3000.0)

    # Ensure seasonality is always a list of 12 floats
    if not isinstance(seasonality, list) or len(seasonality) != 12:
        seasonality = [1.0] * 12
    session['seasonality'] = seasonality

    annual_operating_expenses_value = 0

    # Calculate total annual operating expenses from session data (already numeric)
    if operating_expenses:
        for expense in operating_expenses:
            try:
                amount = float(expense.get('amount', 0))
                if expense['frequency'] == 'monthly':
                    annual_operating_expenses_value += amount * 12
                elif expense['frequency'] == 'quarterly':
                    annual_operating_expenses_value += amount * 4
            except (ValueError, TypeError):
                continue # Skip invalid expense entries
    session['annual_operating_expenses'] = annual_operating_expenses_value
    session['quarterly_operating_expenses'] = annual_operating_expenses_value / 4
    
    # Use default values for cogs_percentage on first pass if not in session
    if 'cogs_percentage' not in session:
        session['cogs_percentage'] = 35.0
    else: # Retrieve from session if it exists
        cogs_percentage = session['cogs_percentage']

    # Calculate forecast for both GET and POST
    forecast = None
    if products:
        # products and operating_expenses are now guaranteed to have numeric values
        forecast = calculate_profitability(
            products=products, 
            cogs_percentage=cogs_percentage, 
            annual_operating_expenses=session.get('annual_operating_expenses', 0),
            tax_rate=tax_rate,
            seasonality_factors=seasonality
        )
        # Refactored: Calculate ratios and add them to the forecast dictionary
        annual_net_profit = forecast.get('annual', {}).get('net_profit', 0)
        annual_revenue = forecast.get('annual', {}).get('revenue', 0)
        quarterly_net_profit = forecast.get('quarterly', {}).get('net_profit', 0)
        quarterly_revenue = forecast.get('quarterly', {}).get('revenue', 0)

        # Update forecast with basic ratios
        forecast['annual'].update(calculate_key_ratios(annual_net_profit, annual_revenue, total_assets))
        forecast['quarterly'].update(calculate_key_ratios(quarterly_net_profit, quarterly_revenue, total_assets))

        # Calculate and add advanced ratios
        annual_tax = forecast.get('annual', {}).get('tax', 0)
        ebitda = annual_net_profit + annual_tax + interest_expense
        operating_cash_flow = annual_net_profit + depreciation
        advanced_ratios = calculate_advanced_ratios(current_assets, current_liabilities, total_debt, total_assets, ebitda, interest_expense, operating_cash_flow)
        forecast['annual'].update(advanced_ratios)

        # For quarterly, we'll scale down the annual inputs for a rough estimate
        quarterly_ebitda = quarterly_net_profit + (annual_tax / 4) + (interest_expense / 4)
        quarterly_ocf = quarterly_net_profit + (depreciation / 4)
        # Note: Using total assets/liabilities for quarterly ratios is a simplification
        quarterly_advanced_ratios = calculate_advanced_ratios(current_assets, current_liabilities, total_debt, total_assets, quarterly_ebitda, interest_expense / 4, quarterly_ocf)
        forecast['quarterly'].update(quarterly_advanced_ratios)

        session['net_profit'] = forecast.get('quarterly', {}).get('net_profit', 0)
        session['annual_net_profit'] = forecast.get('annual', {}).get('net_profit', 0)
        session['total_annual_revenue'] = forecast.get('annual', {}).get('revenue', 0)
        # annual_operating_expenses is already set
    else:
        # Ensure net_profit is cleared if there are no products
        session['net_profit'] = 0
        session['annual_net_profit'] = 0
        session['total_annual_revenue'] = 0
        session['annual_operating_expenses'] = 0

    return render_template('financial-forecast.html', 
                             products=products, 
                             forecast=forecast, 
                             cogs_percentage=cogs_percentage,
                             operating_expenses=operating_expenses,
                             annual_operating_expenses=session.get('annual_operating_expenses', 0),
                             tax_rate=tax_rate,
                             seasonality=seasonality,
                             total_assets=total_assets,
                             current_assets=current_assets,
                             current_liabilities=current_liabilities,
                             total_debt=total_debt,
                             interest_expense=interest_expense,
                             depreciation=depreciation
                             )

@app.route("/recalculate-forecast", methods=["POST"])
def recalculate_forecast():
    data = request.get_json()
    cogs_percentage = float(data.get('cogs_percentage'))
    # The input from the page is now annual
    annual_operating_expenses_value = float(data.get('annual_operating_expenses'))
    tax_rate = float(data.get('tax_rate'))
    seasonality = [float(v) for v in data.get('seasonality', [1.0] * 12)]
    total_assets = float(data.get('total_assets')) # New: Get total assets
    # New ratio inputs
    current_assets = float(data.get('current_assets'))
    current_liabilities = float(data.get('current_liabilities'))
    total_debt = float(data.get('total_debt'))
    interest_expense = float(data.get('interest_expense'))
    depreciation = float(data.get('depreciation'))

    # Get other required data from session
    products = session.get('products', [])
    
    # Update session with the new value
    session['cogs_percentage'] = cogs_percentage
    session['annual_operating_expenses'] = annual_operating_expenses_value
    session['tax_rate'] = tax_rate
    session['seasonality'] = seasonality
    session['total_assets'] = total_assets # New: Save to session
    session['current_assets'] = current_assets
    session['current_liabilities'] = current_liabilities
    session['total_debt'] = total_debt
    session['interest_expense'] = interest_expense
    session['depreciation'] = depreciation

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

    # Update forecast with basic ratios
    forecast['annual'].update(calculate_key_ratios(annual_net_profit, annual_revenue, total_assets))
    forecast['quarterly'].update(calculate_key_ratios(quarterly_net_profit, quarterly_revenue, total_assets))
    
    # Calculate and add advanced ratios
    annual_tax = forecast.get('annual', {}).get('tax', 0)
    ebitda = annual_net_profit + annual_tax + interest_expense
    operating_cash_flow = annual_net_profit + depreciation
    advanced_ratios = calculate_advanced_ratios(current_assets, current_liabilities, total_debt, total_assets, ebitda, interest_expense, operating_cash_flow)
    forecast['annual'].update(advanced_ratios)

    # For quarterly, we'll scale down the annual inputs for a rough estimate
    quarterly_ebitda = quarterly_net_profit + (annual_tax / 4) + (interest_expense / 4)
    quarterly_ocf = quarterly_net_profit + (depreciation / 4)
    # Note: Using total assets/liabilities for quarterly ratios is a simplification
    quarterly_advanced_ratios = calculate_advanced_ratios(current_assets, current_liabilities, total_debt, total_assets, quarterly_ebitda, interest_expense / 4, quarterly_ocf)
    forecast['quarterly'].update(quarterly_advanced_ratios)

    # Also update the session net profit for the loan calculator
    session['net_profit'] = forecast.get('quarterly', {}).get('net_profit', 0)
    session['annual_net_profit'] = forecast.get('annual', {}).get('net_profit', 0)
    session['total_annual_revenue'] = forecast.get('annual', {}).get('revenue', 0)

    return jsonify(forecast)

@app.route("/loan-calculator", methods=['GET', 'POST'])
def loan_calculator():
    quarterly_net_profit = session.get('net_profit')
    monthly_net_profit = quarterly_net_profit / 3 if quarterly_net_profit is not None else 0
    annual_net_profit = session.get('annual_net_profit', 0)
    total_annual_revenue = session.get('total_annual_revenue', 0)
    annual_operating_expenses = session.get('annual_operating_expenses', 0)

    monthly_payment = None
    schedule = None
    # Load existing loan details from session to persist form data
    form_data = session.get('loan_details', {})
    assessment = None
    dscr = 0.0
    dscr_status = ""

    if request.method == 'POST':
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
            # Net Operating Income is often approximated as EBITDA.
            # Here, we'll use Annual Net Profit + Interest portion of debt. Since we don't have interest as a separate input,
            # we'll use a common proxy: Annual Net Profit + Annual Operating Expenses.
            net_operating_income = annual_net_profit
            total_debt_service = monthly_payment * 12

            dscr = calculate_dscr(net_operating_income, total_debt_service)

            if dscr < 1.0:
                dscr_status = ASSESSMENT_MESSAGES['high_risk']['dscr_status']
            elif dscr < 1.25:
                dscr_status = ASSESSMENT_MESSAGES['medium_risk']['dscr_status']
            else:
                dscr_status = ASSESSMENT_MESSAGES['low_risk']['dscr_status']

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
def export_forecast():
    # Gather all necessary data from the session
    products = session.get('products', [])
    operating_expenses = session.get('expenses', [])
    cogs_percentage = session.get('cogs_percentage', 35.0)
    loan_details = session.get('loan_details', {})

    # Generate the spreadsheet file in memory
    spreadsheet_file = create_forecast_spreadsheet(
        products, operating_expenses, cogs_percentage, loan_details
    )

    return send_file(
        spreadsheet_file,
        as_attachment=True,
        download_name='financial_forecast.xlsx',
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )

if __name__ == '__main__':
    # Runs the app on a local development server
    app.run(debug=True)
