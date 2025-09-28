from openpyxl import Workbook
from openpyxl.styles import Font, Alignment, Border, Side, PatternFill
from openpyxl.utils import get_column_letter
from io import BytesIO

def create_forecast_spreadsheet(products, operating_expenses, cogs_percentage, loan_details):
    """
    Creates an Excel spreadsheet with financial forecast and loan amortization data.
    """
    wb = Workbook()

    # --- Sheet 1: Financial Forecast ---
    ws1 = wb.active
    ws1.title = "Financial Forecast"

    # Styles
    header_font = Font(bold=True, color="FFFFFF")
    header_fill = PatternFill(start_color="4F81BD", end_color="4F81BD", fill_type="solid")
    title_font = Font(size=14, bold=True)
    currency_format = '$#,##0.00'

    # Title
    ws1['A1'] = 'Quarterly Sales Forecast Year 1 (USD)'
    ws1['A1'].font = title_font
    ws1.merge_cells('A1:I1')

    # Product Headers
    product_headers = ['Product/Service', 'Price', 'Sales Volume', 'Unit', 'Q1 Revenue', 'Q2 Revenue', 'Q3 Revenue', 'Q4 Revenue', 'Annual Revenue']
    ws1.append(product_headers)
    for cell in ws1[2]:
        cell.font = header_font
        cell.fill = header_fill

    # Product Data
    total_annual_revenue = 0
    for p in products:
        price = p.get('price', 0)
        volume = p.get('sales_volume', 0)
        unit = p.get('sales_volume_unit', 'monthly')
        
        quarterly_volume = volume * 3 if unit == 'monthly' else volume
        quarterly_revenue = price * quarterly_volume
        annual_revenue = quarterly_revenue * 4
        total_annual_revenue += annual_revenue

        row_data = [
            p.get('description', 'N/A'), price, volume, unit.capitalize(),
            quarterly_revenue, quarterly_revenue, quarterly_revenue, quarterly_revenue,
            annual_revenue
        ]
        ws1.append(row_data)

    # Apply currency formatting to revenue columns
    for row in ws1.iter_rows(min_row=3, max_row=ws1.max_row, min_col=5, max_col=9):
        for cell in row:
            cell.number_format = currency_format
    ws1['B3'].number_format = currency_format

    # --- Sheet 2: Loan Amortization ---
    if loan_details and loan_details.get('schedule'):
        ws2 = wb.create_sheet(title="Loan Amortization")

        # Loan Summary
        ws2['A1'] = 'Loan Summary'
        ws2['A1'].font = title_font
        ws2.append(['Loan Amount', loan_details.get('loan_amount')])
        ws2.append(['Annual Interest Rate (%)', loan_details.get('interest_rate')])
        ws2.append(['Loan Term (Years)', loan_details.get('loan_term')])
        ws2.append(['Monthly Payment', loan_details.get('monthly_payment')])
        
        # Apply formatting to summary
        for row_num in range(2, 6):
            ws2[f'B{row_num}'].number_format = currency_format if row_num in [2, 5] else '0.00'

        # Amortization Schedule Headers
        schedule_headers = ['Month', 'Principal Payment', 'Interest Payment', 'Remaining Balance']
        ws2.append([]) # Spacer row
        ws2.append(schedule_headers)
        for cell in ws2[7]:
            cell.font = header_font
            cell.fill = header_fill

        # Schedule Data
        for item in loan_details['schedule']:
            ws2.append([
                item['month'],
                item['principal_payment'],
                item['interest_payment'],
                item['remaining_balance']
            ])
        
        # Apply currency formatting to schedule
        for row in ws2.iter_rows(min_row=8, max_row=ws2.max_row, min_col=2, max_col=4):
            for cell in row:
                cell.number_format = currency_format

    # Adjust column widths for all sheets
    for sheet in wb.worksheets:
        for col in sheet.columns:
            max_length = 0
            # Get the column letter from the second cell in the column
            # to avoid issues with merged cells in the first row (like the title).
            # This assumes every sheet has at least 2 rows.
            column = col[1].column_letter
            for cell in col:
                try:
                    if len(str(cell.value)) > max_length:
                        max_length = len(str(cell.value))
                except:
                    pass
            adjusted_width = (max_length + 2)
            sheet.column_dimensions[column].width = adjusted_width

    # Save to an in-memory file
    in_memory_file = BytesIO()
    wb.save(in_memory_file)
    in_memory_file.seek(0)
    return in_memory_file