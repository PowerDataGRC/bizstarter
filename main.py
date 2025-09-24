import os

from flask import Flask, render_template

app = Flask(__name__, template_folder='templates', static_folder='static')

@app.route("/")
def intro():
    return render_template('intro.html')

@app.route("/product-detail")
def product_detail():
    return render_template('product-detail.html')

@app.route("/financial-forecast")
def financial_forecast():
    return render_template('financial-forecast.html')

@app.route("/loan-calculator")
def loan_calculator():
    return render_template('loan-calculator.html')

def main():
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8080)))

if __name__ == "__main__":
    main()
