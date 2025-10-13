document.addEventListener('DOMContentLoaded', () => {
    // --- Number Formatting for Loan Amount Input ---
    const loanAmountInput = document.getElementById('loan_amount');

    if (loanAmountInput) {
        const formatNumberInput = (num) => {
            if (num === null || num === undefined || num === '') return '';
            const number = parseFloat(String(num).replace(/,/g, ''));
            return isNaN(number) ? '' : number.toLocaleString('en-US', { maximumFractionDigits: 0 });
        };

        loanAmountInput.addEventListener('input', (e) => {
            const value = e.target.value;
            const numericValue = parseFormattedNumber(value);
            const formattedValue = formatNumberInput(numericValue);
            e.target.value = formattedValue;
        });

        loanAmountInput.addEventListener('focus', (e) => {
            e.target.value = parseFormattedNumber(e.target.value) || '';
        });

        loanAmountInput.form.addEventListener('submit', () => {
            loanAmountInput.value = parseFormattedNumber(loanAmountInput.value);
        });
    }

    // --- Charting Logic ---
    const chartContainer = document.getElementById('chart-container');
    if (!chartContainer) return; // Don't run chart logic if there's no chart

    const scheduleData = JSON.parse(chartContainer.dataset.schedule);
    const loanTermInYears = parseInt(chartContainer.dataset.loanTerm, 10);

    if (!scheduleData || !loanTermInYears) return;

    const ctx = document.getElementById('loanChart').getContext('2d');
    const backButton = document.getElementById('back-to-yearly');
    const chartControls = document.getElementById('chart-controls');
    let loanChart;

    const currencyFormatter = new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' });
    const tooltipOptions = { callbacks: { label: (c) => `${c.dataset.label || ''}: ${currencyFormatter.format(c.parsed.y)}` } };

    function drawMonthlyChart(data, title) {
        if (loanChart) loanChart.destroy();
        loanChart = new Chart(ctx, {
            type: 'bar',
            data: {
                labels: data.map(item => `Month ${item.month}`),
                datasets: [
                    { label: 'Principal', data: data.map(item => item.principal_payment), backgroundColor: 'rgba(54, 162, 235, 0.7)' },
                    { label: 'Interest', data: data.map(item => item.interest_payment), backgroundColor: 'rgba(255, 99, 132, 0.7)' }
                ]
            },
            options: {
                responsive: true, maintainAspectRatio: false,
                scales: { x: { stacked: true }, y: { stacked: true } },
                plugins: { title: { display: true, text: title, font: { size: 14 } }, tooltip: tooltipOptions }
            }
        });
    }

    function drawYearlyChart() {
        if (loanChart) loanChart.destroy();
        const yearlyAggregates = {};
        scheduleData.forEach(item => {
            const year = Math.ceil(item.month / 12);
            if (!yearlyAggregates[year]) yearlyAggregates[year] = { year: year, principal: 0, interest: 0 };
            yearlyAggregates[year].principal += item.principal_payment;
            yearlyAggregates[year].interest += item.interest_payment;
        });
        const yearlyData = Object.values(yearlyAggregates);
        loanChart = new Chart(ctx, {
            type: 'bar',
            data: {
                labels: yearlyData.map(item => `Year ${item.year}`),
                datasets: [
                    { label: 'Total Principal', data: yearlyData.map(item => item.principal), backgroundColor: 'rgba(54, 162, 235, 0.7)' },
                    { label: 'Total Interest', data: yearlyData.map(item => item.interest), backgroundColor: 'rgba(255, 99, 132, 0.7)' }
                ]
            },
            options: {
                responsive: true, maintainAspectRatio: false,
                onClick: (event, elements) => {
                    if (elements.length > 0) {
                        const selectedYear = yearlyData[elements[0].index].year;
                        const monthlyData = scheduleData.filter(item => Math.ceil(item.month / 12) === selectedYear);
                        drawMonthlyChart(monthlyData, `Monthly Breakdown for Year ${selectedYear}`);
                        chartControls.style.display = 'block';
                    }
                },
                scales: { x: { stacked: true, title: { display: true, text: 'Year (Click for details)' } }, y: { stacked: true } },
                plugins: { title: { display: true, text: 'Yearly Loan Payment Summary', font: { size: 14 } }, tooltip: tooltipOptions }
            }
        });
        chartControls.style.display = 'none';
    }

    if (loanTermInYears >= 2) {
        drawYearlyChart();
    } else {
        drawMonthlyChart(scheduleData, 'Monthly Loan Payment Schedule');
    }

    backButton.addEventListener('click', () => drawYearlyChart());
});