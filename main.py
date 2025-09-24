import os
import json
from flask import Flask, render_template, request, session, jsonify
from profitability import calculate_profitability
from loan import calculate_loan_schedule

app = Flask(__name__)
app.secret_key = os.urandom(24)

# Load assessment messages from JSON file
with open('assessment_messages.json') as f:
    ASSESSMENT_MESSAGES = json.load(f)

@app.route("/")
def index():
    return render_template('intro.html')

@app.route("/product-detail")
def product_detail():
    # Check if starting over from the intro page
    if request.args.get('startover'):
        # Clear session data when starting over
        session.clear()
        products = []
    else:
        # Load products from session if they exist
        products = session.get('products', [])
        
    return render_template('product-detail.html', products=products)

@app.route("/financial-forecast", methods=["GET", "POST"])
def financial_forecast():
    products = session.get('products', [])
    cogs_percentage = session.get('cogs_percentage', 35.0)
    quarterly_operating_expenses = session.get('quarterly_operating_expenses', 5000.0)

    if request.method == "POST":
        # Form submission from product-detail page
        products = []
        for i in range(1, 9):
            desc = request.form.get(f'product_description_{i}')
            price_str = request.form.get(f'price_{i}')
            volume_str = request.form.get(f'sales_volume_{i}')
            unit = request.form.get(f'sales_volume_unit_{i}')

            if desc and price_str and volume_str and unit:
                try:
                    price = float(price_str)
                    volume = int(volume_str)
                    products.append({
                        "description": desc,
                        "price": price,
                        "sales_volume": volume,
                        "sales_volume_unit": unit
                    })
                except (ValueError, TypeError):
                    continue
        
        session['products'] = products
        # Use default values for forecast params on first pass
        cogs_percentage = 35.0
        quarterly_operating_expenses = 5000.0
        session['cogs_percentage'] = cogs_percentage
        session['quarterly_operating_expenses'] = quarterly_operating_expenses

    # Calculate forecast for both GET and POST
    forecast = None
    if products:
        forecast = calculate_profitability(products, cogs_percentage, quarterly_operating_expenses)
        session['net_profit'] = forecast.get('quarterly', {}).get('net_profit', 0)
    else:
        # Ensure net_profit is cleared if there are no products
        session['net_profit'] = 0

    return render_template('financial-forecast.html', 
                             products=products, 
                             forecast=forecast, 
                             cogs_percentage=cogs_percentage,
                             quarterly_operating_expenses=quarterly_operating_expenses)

@app.route("/recalculate-forecast", methods=["POST"])
def recalculate_forecast():
    data = request.get_json()
    cogs_percentage = float(data.get('cogs_percentage'))
    quarterly_operating_expenses = float(data.get('quarterly_operating_expenses'))

    # Get other required data from session
    products = session.get('products', [])
    
    # Update session with the new value
    session['cogs_percentage'] = cogs_percentage
    session['quarterly_operating_expenses'] = quarterly_operating_expenses

    if not products:
        return jsonify({'error': 'No product data in session'}), 400

    forecast = calculate_profitability(products, cogs_percentage, quarterly_operating_expenses)
    
    # Also update the session net profit for the loan calculator
    session['net_profit'] = forecast.get('quarterly', {}).get('net_profit', 0)

    return jsonify(forecast)

@app.route("/loan-calculator", methods=['GET', 'POST'])
def loan_calculator():
    quarterly_net_profit = session.get('net_profit')
    monthly_net_profit = quarterly_net_profit / 3 if quarterly_net_profit is not None else 0
    
    monthly_payment = None
    schedule = None
    form_data = {}
    assessment = None

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

        if monthly_payment is not None and monthly_payment > 0:
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
                           schedule=schedule)

def main():
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8080)), debug=True)

if __name__ == "__main__":
    main()