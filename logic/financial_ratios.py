def calculate_dscr(net_operating_income, total_debt_service):
    """
    Calculates the Debt Service Coverage Ratio (DSCR).

    NOI (Net Operating Income) / Total Debt Service
    """
    if total_debt_service <= 0:
        return 0.0 # Or handle as an error/undefined
    return net_operating_income / total_debt_service

def calculate_key_ratios(net_profit, total_revenue, total_assets, current_assets,
                         current_liabilities, total_debt, net_operating_income,
                         interest_expense, depreciation):
    """
    Calculates a comprehensive set of key financial ratios.

    :param net_profit: The net profit for the period.
    :param total_revenue: The total revenue for the period.
    :param total_assets: The total assets of the business.
    :param current_assets: Current assets.
    :param current_liabilities: Current liabilities.
    :param total_debt: Total debt.
    :param net_operating_income: Net Operating Income (EBIT).
    :param interest_expense: Annual interest expense.
    :param depreciation: Annual depreciation.
    :return: A dictionary containing key financial ratios.
    """
    # Profitability Ratios
    profit_margin = (net_profit / total_revenue) * 100 if total_revenue > 0 else 0
    roa = (net_profit / total_assets) * 100 if total_assets > 0 else 0

    # Current Ratio (Liquidity)
    current_ratio = current_assets / current_liabilities if current_liabilities > 0 else 0

    # Debt-to-Equity Ratio (Leverage/Solvency)
    total_equity = total_assets - total_debt
    debt_to_equity_ratio = total_debt / total_equity if total_equity > 0 else 0

    # EBITDA = EBIT + Depreciation
    ebitda = net_operating_income + depreciation

    # Interest Coverage Ratio (ICR)
    interest_coverage_ratio = ebitda / interest_expense if interest_expense > 0 else 0

    # Operating Cash Flow Ratio
    # A common approximation for OCF is Net Income + Depreciation + Interest Expense.
    # This represents the cash generated from operations before accounting for changes in working capital.
    operating_cash_flow = net_profit + depreciation + interest_expense
    operating_cash_flow_ratio = operating_cash_flow / current_liabilities if current_liabilities > 0 else 0

    return {
        "profit_margin": profit_margin,
        "roa": roa,
        "current_ratio": current_ratio,
        "debt_to_equity_ratio": debt_to_equity_ratio,
        "interest_coverage_ratio": interest_coverage_ratio,
        "operating_cash_flow_ratio": operating_cash_flow_ratio
    }
