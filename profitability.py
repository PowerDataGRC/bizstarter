def calculate_profitability(products, cogs_percentage=35.0, quarterly_operating_expenses=5000.0):
    """
    Calculates the annual and quarterly financial forecast based on product sales and operational costs.
    """
    # Ensure numeric types, providing defaults if None
    cogs_percentage = float(cogs_percentage) if cogs_percentage is not None else 35.0
    quarterly_operating_expenses = float(quarterly_operating_expenses) if quarterly_operating_expenses is not None else 5000.0

    # Calculate total annual revenue from all products
    total_annual_revenue = 0
    for p in products:
        if p['sales_volume_unit'] == 'monthly':
            annual_volume = p['sales_volume'] * 12
        else:  # Assumes quarterly
            annual_volume = p['sales_volume'] * 4
        total_annual_revenue += p['price'] * annual_volume

    # Calculate annual costs
    annual_operating_expenses = quarterly_operating_expenses * 4
    cost_of_goods_sold = total_annual_revenue * (cogs_percentage / 100)
    gross_profit = total_annual_revenue - cost_of_goods_sold
    annual_net_profit = gross_profit - annual_operating_expenses

    # Calculate profit margin
    profit_margin = (annual_net_profit / total_annual_revenue) * 100 if total_annual_revenue != 0 else 0
    
    # Derive quarterly figures from annual results
    quarterly_revenue = total_annual_revenue / 4
    quarterly_net_profit = annual_net_profit / 4

    return {
        "annual": {
            "revenue": total_annual_revenue,
            "net_profit": annual_net_profit,
            "profit_margin": profit_margin
        },
        "quarterly": {
            "revenue": quarterly_revenue,
            "net_profit": quarterly_net_profit,
            "profit_margin": profit_margin
        }
    }
