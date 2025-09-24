def calculate_loan_schedule(principal, annual_interest_rate, loan_term_years):
    """
    Calculates the monthly loan payment and generates a full amortization schedule.
    """
    if principal <= 0 or annual_interest_rate < 0 or loan_term_years <= 0:
        return {"monthly_payment": 0, "schedule": []}

    # Convert annual rate to monthly and term to months
    monthly_interest_rate = (annual_interest_rate / 100) / 12
    number_of_payments = loan_term_years * 12

    if monthly_interest_rate == 0:
        monthly_payment = principal / number_of_payments if number_of_payments > 0 else 0
    else:
        # Monthly payment formula
        monthly_payment = principal * (monthly_interest_rate * (1 + monthly_interest_rate) ** number_of_payments) / ((1 + monthly_interest_rate) ** number_of_payments - 1)

    # Generate amortization schedule
    schedule = []
    remaining_balance = principal
    for i in range(1, number_of_payments + 1):
        interest_payment = remaining_balance * monthly_interest_rate
        principal_payment = monthly_payment - interest_payment
        remaining_balance -= principal_payment
        
        # Ensure balance doesn't go negative due to floating point inaccuracies
        if remaining_balance < 0: remaining_balance = 0

        schedule.append({
            "month": i,
            "interest_payment": interest_payment,
            "principal_payment": principal_payment,
            "remaining_balance": remaining_balance
        })

    return {
        "monthly_payment": monthly_payment,
        "schedule": schedule
    }
