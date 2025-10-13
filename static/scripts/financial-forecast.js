// Function to format numbers as currency
const formatCurrency = (value) => {
    return new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' }).format(value);
};

// --- Number Formatting ---
const formatNumberInput = (num) => {
    if (num === null || num === undefined || num === '') return '';
    const number = parseFloat(String(num).replace(/,/g, ''));
    return isNaN(number) ? '' : number.toLocaleString('en-US');
};

const parseFormattedNumber = (str) => {
    if (typeof str !== 'string') return str;
    return parseFloat(str.replace(/,/g, '')) || 0;
};

let cashFlowChart;
let revenueExpenseChart;
const drawCashFlowChart = () => {
    if (!forecastData || !forecastData.monthly) return;

    const ctx = document.getElementById('cashFlowChart').getContext('2d');
    const labels = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
    const data = forecastData.monthly.map(m => m.net_profit);

    if (cashFlowChart) {
        cashFlowChart.data.datasets[0].data = data; // Update data
        cashFlowChart.update();
    } else {
        cashFlowChart = new Chart(ctx, {
            type: 'bar',
            data: {
                labels: labels,
                datasets: [{
                    label: 'Monthly Net Profit',
                    data: data,
                    backgroundColor: data.map(v => v < 0 ? 'rgba(255, 99, 132, 0.7)' : 'rgba(75, 192, 192, 0.7)'),
                    borderColor: data.map(v => v < 0 ? 'rgba(255, 99, 132, 1)' : 'rgba(75, 192, 192, 1)'),
                    borderWidth: 1
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                scales: { y: { beginAtZero: true } },
                plugins: { tooltip: { callbacks: { label: (c) => `Net Profit: ${formatCurrency(c.raw)}` } } }
            }
        });
    }
};

const drawRevenueExpenseChart = () => {
    if (!forecastData || !forecastData.monthly) return;

    const ctx = document.getElementById('revenueExpenseChart').getContext('2d');
    const labels = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
    const revenueData = forecastData.monthly.map(m => m.revenue);
    const expenseData = forecastData.monthly.map(m => m.cogs + m.operating_expenses + m.tax); // Total expenses including tax
    const netProfitData = forecastData.monthly.map(m => m.net_profit);

    if (revenueExpenseChart) {
        revenueExpenseChart.data.datasets[0].data = expenseData;
        revenueExpenseChart.data.datasets[1].data = netProfitData;
        revenueExpenseChart.update();
    } else {
        revenueExpenseChart = new Chart(ctx, {
            type: 'bar',
            data: {
                labels: labels,
                datasets: [{
                    label: 'Total Expenses (COGS + OpEx + Tax)',
                    data: expenseData,
                    backgroundColor: 'rgba(255, 159, 64, 0.7)',
                }, {
                    label: 'Net Profit',
                    data: netProfitData,
                    backgroundColor: 'rgba(75, 192, 192, 0.7)',
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                scales: {
                    x: {
                        stacked: true,
                    },
                    y: {
                        stacked: true,
                        beginAtZero: true
                    }
                },
                plugins: {
                    tooltip: { callbacks: { label: (c) => `${c.dataset.label}: ${formatCurrency(c.raw)}` } }
                }
            }
        });
    }
};

// Function to update the display based on the selected view
const updateDisplay = (view) => {
    if (!forecastData) return;

    const data = forecastData[view];
    document.getElementById('revenue-display').textContent = formatCurrency(data.revenue);
    document.getElementById('net-profit-display').textContent = formatCurrency(data.net_profit || 0);
    document.getElementById('profit-margin-display').textContent = (data.profit_margin || 0).toFixed(2) + '%';
    document.getElementById('roa-display').textContent = (data.roa || 0).toFixed(2) + '%';
    document.getElementById('current-ratio-display').textContent = (data.current_ratio || 0).toFixed(2);
    document.getElementById('de-ratio-display').textContent = (data.debt_to_equity_ratio || 0).toFixed(2);
    document.getElementById('icr-display').textContent = (data.interest_coverage_ratio || 0).toFixed(2);
    document.getElementById('ocf-ratio-display').textContent = (data.operating_cash_flow_ratio || 0).toFixed(2);
};

const initializeForecastPage = () => {
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initializeForecastPage);
        return;
    }

    console.log('Initializing forecast page...');

    // --- Recalculation Logic ---
    const cogsSlider = document.getElementById('cogsPercentage');
    const cogsValue = document.getElementById('cogsValue');
    const taxSlider = document.getElementById('taxRate');
    const taxValue = document.getElementById('taxRateValue');
    const annualExpensesInput = document.getElementById('annualExpenses');
    const totalAssetsInput = document.getElementById('totalAssets');
    const totalLiabilitiesInput = document.getElementById('totalLiabilities');
    const depreciationInput = document.getElementById('depreciation');
    const interestExpenseInput = document.getElementById('interestExpense');
    const seasonalityInputs = document.querySelectorAll('.seasonality-input');

    // Initial display update
    drawCashFlowChart();
    drawRevenueExpenseChart();
    updateDisplay('annual'); // Default to annual view

    document.getElementById('annual-view')?.addEventListener('change', () => updateDisplay('annual'));
    document.getElementById('quarterly-view')?.addEventListener('change', () => updateDisplay('quarterly'));

    // --- Seasonality Button State ---
    const normalizeBtn = document.getElementById('normalize-seasonality');
    const setNormalizeBtnActive = (isActive) => {
        normalizeBtn.classList.toggle('btn-primary', isActive);
        normalizeBtn.classList.toggle('btn-outline-secondary', !isActive);
    };

    // --- Itemized List Management ---
    const updateTotals = () => {
        const totalAssets = Array.from(document.querySelectorAll('.asset-amount')).reduce((sum, input) => sum + parseFormattedNumber(input.value), 0);
        totalAssetsInput.value = formatNumberInput(totalAssets);

        const totalLiabilities = Array.from(document.querySelectorAll('.liability-amount')).reduce((sum, input) => sum + parseFormattedNumber(input.value), 0);
        totalLiabilitiesInput.value = formatNumberInput(totalLiabilities);
    };

    const recalculate = () => {
        updateTotals(); // Update the total fields before sending data

        const cogs = cogsSlider.value;
        const expenses = parseFormattedNumber(annualExpensesInput.value);
        const tax = taxSlider.value;
        const depreciation = parseFormattedNumber(depreciationInput.value);
        const interestExpense = parseFormattedNumber(interestExpenseInput.value);
        const seasonality = Array.from(seasonalityInputs).map(input => parseFloat(input.value) || 0);

        const assetsList = Array.from(document.querySelectorAll('#assets-table-body tr')).map(row => ({
            description: row.querySelector('.asset-description').value,
            amount: parseFormattedNumber(row.querySelector('.asset-amount').value)
        }));

        const liabilitiesList = Array.from(document.querySelectorAll('#liabilities-table-body tr')).map(row => ({
            description: row.querySelector('.liability-description').value,
            amount: parseFormattedNumber(row.querySelector('.liability-amount').value)
        }));

        const totalAssets = parseFormattedNumber(totalAssetsInput.value);
        const totalLiabilities = parseFormattedNumber(totalLiabilitiesInput.value);

        cogsValue.textContent = cogs;
        taxValue.textContent = tax;

        fetch('/recalculate-forecast', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                cogs_percentage: cogs,
                annual_operating_expenses: expenses,
                tax_rate: tax,
                seasonality: seasonality,
                assets: assetsList,
                liabilities: liabilitiesList,
                depreciation: depreciation,
                current_assets: totalAssets,
                current_liabilities: totalLiabilities,
                interest_expense: interestExpense
            }),
        })
            .then(response => response.json())
            .then(newForecast => {
                // Update the global forecast data
                forecastData.annual = newForecast.annual;
                forecastData.quarterly = newForecast.quarterly;
                forecastData.monthly = newForecast.monthly;

                // Update the display based on the currently selected view
                const selectedView = document.getElementById('annual-view').checked ? 'annual' : 'quarterly';
                updateDisplay(selectedView);
                drawCashFlowChart(); // Redraw the cash flow chart
                drawRevenueExpenseChart(); // Redraw the new revenue/expense chart
            })
            .catch(error => console.error('Error recalculating forecast:', error));
    };

    const inputsForRecalculation = [
        cogsSlider, taxSlider, annualExpensesInput, depreciationInput, interestExpenseInput
    ];

    inputsForRecalculation.forEach(input => input?.addEventListener('input', recalculate));

    if (seasonalityInputs) {
        seasonalityInputs.forEach(input => input.addEventListener('input', () => {
            recalculate();
            setNormalizeBtnActive(true); // Make button active on input change
        }));
    }

    const setupTableEventListeners = (tableBodyId, addBtnId, descClass, amountClass) => {
        const tableBody = document.getElementById(tableBodyId);

        if (tableBody) {
            // Use event delegation for handling clicks on remove buttons
            tableBody.addEventListener('click', (e) => {
                if (e.target && e.target.classList.contains('remove-row-btn')) {
                    e.target.closest('tr').remove();
                    recalculate(); // updateTotals() is called within recalculate
                }
            });

            // Use event delegation for handling input on amount fields
            tableBody.addEventListener('input', (e) => {
                if (e.target && e.target.classList.contains(amountClass)) {
                    recalculate();
                }
            });
        }
    };

    const addRow = (tbodyId, descClass, amountClass) => {
        const tbody = document.getElementById(tbodyId);
        const newRow = document.createElement('tr');
        newRow.innerHTML = `
            <td><input type="text" class="form-control form-control-sm ${descClass}" value=""></td>
            <td><input type="text" class="form-control form-control-sm number-input ${amountClass}" value="0"></td>
            <td><button class="btn btn-sm btn-outline-danger remove-row-btn">&times;</button></td>
        `;
        tbody.appendChild(newRow);
        newRow.querySelector('.number-input').addEventListener('focusout', (e) => {
            e.target.value = formatNumberInput(e.target.value);
        });
    };

    setupTableEventListeners('assets-table-body', 'add-asset-btn', 'asset-description', 'asset-amount');
    setupTableEventListeners('liabilities-table-body', 'add-liability-btn', 'liability-description', 'liability-amount');

    document.getElementById('add-asset-btn')?.addEventListener('click', () => addRow('assets-table-body', 'asset-description', 'asset-amount'));
    document.getElementById('add-liability-btn')?.addEventListener('click', () => addRow('liabilities-table-body', 'liability-description', 'liability-amount'));

    // Seasonality normalization
    if (normalizeBtn) {
        normalizeBtn.addEventListener('click', () => {
            const inputs = Array.from(seasonalityInputs);
            const values = inputs.map(input => parseFloat(input.value) || 0);
            const total = values.reduce((sum, val) => sum + val, 0);

            if (total > 0) {
                const normalizedValues = values.map(val => (val / total) * 12);
                inputs.forEach((input, index) => {
                    input.value = normalizedValues[index].toFixed(2);
                });
                recalculate(); // Trigger recalculation after normalizing
                setNormalizeBtnActive(false); // Revert button to original state
            }
        });
    }
};

// Initialize the page
initializeForecastPage();

// Error logging for script load
console.log('financial-forecast.js loaded. If you see this, the script is working.');
