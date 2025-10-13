def calculate_profitability(products, cogs_percentage=35.0, annual_operating_expenses=0.0, tax_rate=8.0, seasonality_factors=None):
    """
    Calculates a monthly, quarterly, and annual financial forecast.

    :param products: List of product data.
    :param cogs_percentage: Cost of Goods Sold as a percentage of revenue.
    :param annual_operating_expenses: Total annual operating expenses.
    :param tax_rate: The tax rate on profit before tax.
    :param seasonality_factors: A list of 12 factors for each month.
    """
    if seasonality_factors is None:
        seasonality_factors = [1.0] * 12

    # --- 1. Calculate Base Annual Revenue (unadjusted for seasonality) ---
    base_annual_revenue = 0
    for p in products:
        # Ensure numeric types from product data
        p['price'] = float(p.get('price', 0) or 0)
        p['sales_volume'] = int(p.get('sales_volume', 0) or 0)
        if p['sales_volume_unit'] == 'monthly':
            annual_volume = p['sales_volume'] * 12
        else:  # Assumes quarterly
            annual_volume = p['sales_volume'] * 4
        base_annual_revenue += p['price'] * annual_volume

    # --- 2. Calculate monthly breakdown ---
    monthly_forecasts = []
    base_monthly_revenue = base_annual_revenue / 12 if base_annual_revenue > 0 else 0
    monthly_op_ex = annual_operating_expenses / 12
    
    # Normalize seasonality factors so their sum is 12 (average is 1)
    total_factor = sum(seasonality_factors)
    if total_factor == 0: # Avoid division by zero
        normalized_factors = [1.0] * 12
    else:
        normalized_factors = [(f / total_factor) * 12 for f in seasonality_factors]

    for i in range(12):
        month = i + 1
        revenue = base_monthly_revenue * normalized_factors[i]
        cogs = revenue * (cogs_percentage / 100)
        gross_profit = revenue - cogs
        pbt = gross_profit - monthly_op_ex # Profit Before Tax
        tax = pbt * (tax_rate / 100) if pbt > 0 else 0
        net_profit = pbt - tax
        
        monthly_forecasts.append({
            "month": month,
            "revenue": revenue,
            "cogs": cogs,
            "gross_profit": gross_profit,
            "operating_expenses": monthly_op_ex,
            "net_profit": net_profit,
            "tax": tax
        })

    # --- 3. Aggregate into Quarterly and Annual summaries ---
    def aggregate_forecast(forecasts):
        total_revenue = sum(f['revenue'] for f in forecasts)
        total_net_profit = sum(f['net_profit'] for f in forecasts)
        total_tax = sum(f['tax'] for f in forecasts)
        total_gross_profit = sum(f['gross_profit'] for f in forecasts)
        return {
            "revenue": total_revenue,
            "net_profit": total_net_profit,
            "tax": total_tax,
            "gross_profit": total_gross_profit
        }

    annual_summary = aggregate_forecast(monthly_forecasts)

    quarterly_summaries = []
    for q in range(4):
        start_index = q * 3
        end_index = start_index + 3
        quarterly_forecasts = monthly_forecasts[start_index:end_index]
        quarterly_summaries.append(aggregate_forecast(quarterly_forecasts))

    # Calculate the average of the quarterly summaries
    average_quarterly_summary = {
        "revenue": sum(q['revenue'] for q in quarterly_summaries) / 4,
        "net_profit": sum(q['net_profit'] for q in quarterly_summaries) / 4,
        "tax": sum(q['tax'] for q in quarterly_summaries) / 4,
        "gross_profit": sum(q['gross_profit'] for q in quarterly_summaries) / 4,
    } if quarterly_summaries else aggregate_forecast([])

    return {
        "monthly": monthly_forecasts,
        "quarterly": average_quarterly_summary,
        "annual": annual_summary
    }
