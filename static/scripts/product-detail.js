document.addEventListener('DOMContentLoaded', () => {
    const productEntriesGrid = document.getElementById('product-entries-grid');
    const addProductBtn = document.getElementById('addProductBtn');
    const expenseEntriesGrid = document.getElementById('expense-entries-grid');
    const addExpenseBtn = document.getElementById('addExpenseBtn');
    const saveDataBtn = document.getElementById('saveDataBtn');
    const saveAndContinueBtn = document.getElementById('saveAndContinueBtn');
    const pageData = JSON.parse(document.getElementById('page-data').textContent);

    // Initialize with data passed from Flask
    let allProductsData = pageData.products || [];
    let allExpensesData = pageData.expenses || [];

    const createProductEntryHTML = (index, product = {}) => {
        return `
            <div class="row product-entry mb-2 align-items-end" data-product-index="${index}">
                <div class="col-md-4 mb-2">
                    <label class="form-label visually-hidden">Product Description</label>
                    <input type="text" class="form-control" name="product_description_${index}" placeholder="Product/Service ${index}" value="${product.description || ''}" required>
                </div>
                <div class="col-md-2 mb-2">
                    <label class="form-label visually-hidden">Price ($)</label>
                    <input type="text" class="form-control number-input" name="price_${index}" placeholder="Price" value="${formatNumber(product.price)}" title="Price ($)" required>
                </div>
                <div class="col-md-2 mb-2">
                    <label class="form-label visually-hidden">Sales Volume</label>
                    <input type="text" class="form-control number-input" name="sales_volume_${index}" placeholder="Volume" value="${formatNumber(product.sales_volume)}" title="Sales Volume" required>
                </div>
                <div class="col-md-2 mb-2">
                    <label class="form-label visually-hidden">Unit</label>
                    <select class="form-select" name="sales_volume_unit_${index}">
                        <option value="monthly" ${product.sales_volume_unit === 'monthly' ? 'selected' : ''}>Monthly</option>
                        <option value="quarterly" ${product.sales_volume_unit === 'quarterly' ? 'selected' : ''}>Quarterly</option>
                    </select>
                </div>
                <div class="col-md-1 mb-2">
                    <i class="bi bi-trash-fill text-danger remove-product-btn" style="cursor: pointer; font-size: 1.2rem;" title="Remove item"></i>
                </div>
            </div>
        `;
    };

    const collectAllProductInputs = (container) => {
        const collectedData = [];
        const allEntryElements = container.querySelectorAll('.product-entry');

        allEntryElements.forEach(entry => {
            const description = entry.querySelector('[name^="product_description_"]').value;
            const price = parseFormattedNumber(entry.querySelector('[name^="price_"]').value);
            const salesVolume = parseFormattedNumber(entry.querySelector('[name^="sales_volume_"]').value);
            const salesVolumeUnit = entry.querySelector('[name^="sales_volume_unit_"]').value;

            if (description || price || salesVolume) {
                collectedData.push({
                    description: description,
                    price: price,
                    sales_volume: salesVolume,
                    sales_volume_unit: salesVolumeUnit
                });
            }
        });
        return collectedData;
    };

    const renderProducts = () => {
        productEntriesGrid.innerHTML = ''; // Clear existing entries
        allProductsData.forEach((product, index) => {
            productEntriesGrid.insertAdjacentHTML('beforeend', createProductEntryHTML(index + 1, product));
        });
        updateTotalSales();
    };

    const updateTotalSales = () => {
        let totalAnnualRevenue = 0;
        allProductsData.forEach(product => {
            const price = parseFloat(product.price) || 0;
            const salesVolume = parseFloat(product.sales_volume) || 0;
            const multiplier = product.sales_volume_unit === 'monthly' ? 12 : 4;
            totalAnnualRevenue += price * salesVolume * multiplier;
        });
        document.getElementById('total-sales').value = totalAnnualRevenue.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
    };

    // Expense Functions
    const createExpenseEntryHTML = (index, expense = {}) => {
        const frequencies = [{ value: 'monthly', text: 'Monthly' }, { value: 'quarterly', text: 'Quarterly' }];
        const isReadonly = expense.readonly || false;
        let optionsHTML = frequencies.map(freq =>
            `<option value="${freq.value}" ${expense.frequency === freq.value ? 'selected' : ''}>${freq.text}</option>`
        ).join('');

        return `
            <div class="row expense-entry mb-2 align-items-end" data-expense-index="${index}">
                <div class="col-md-4 mb-2">
                    <label class="form-label visually-hidden">Expense Item</label>
                    <input type="text" class="form-control" name="expense_item_${index}" placeholder="Expense Item ${index}" value="${expense.item || ''}" ${isReadonly ? 'readonly' : ''} required>
                </div>
                <div class="col-md-3 mb-2">
                    <label class="form-label visually-hidden">Amount ($)</label>
                    <input type="text" class="form-control expense-amount number-input" name="expense_amount_${index}" placeholder="Amount" value="${formatNumber(expense.amount)}" required>
                </div>
                <div class="col-md-3 mb-2">
                    <label class="form-label visually-hidden">Frequency</label>
                    <select class="form-select expense-frequency" name="expense_frequency_${index}">${optionsHTML}</select>
                </div>
                ${!isReadonly ? `<div class="col-md-1 mb-2"><i class="bi bi-trash-fill text-danger remove-expense-btn" style="cursor: pointer; font-size: 1.2rem;" title="Remove item"></i></div>` : '<div class="col-md-1 mb-2"></div>'}
            </div>
        `;
    };

    const renderExpenses = () => {
        expenseEntriesGrid.innerHTML = '';
        allExpensesData.forEach((expense, index) => {
            expenseEntriesGrid.insertAdjacentHTML('beforeend', createExpenseEntryHTML(index + 1, expense));
        });
    };

    const saveDataToSession = async () => {
        try {
            const response = await fetch(pageData.save_url, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    products: allProductsData,
                    expenses: allExpensesData,
                    company_name: document.getElementById('companyName').value
                }),
            });
            if (!response.ok) {
                console.error('Failed to save data');
                saveDataBtn.textContent = 'Save Failed';
                saveDataBtn.classList.replace('btn-info', 'btn-danger');
            } else {
                saveDataBtn.textContent = 'Saved!';
                setTimeout(() => { saveDataBtn.textContent = 'Save Changes'; }, 2000);
            }
        } catch (error) {
            console.error('Error saving data:', error);
        }
    };

    // --- Event Listeners ---
    addProductBtn.addEventListener('click', () => {
        allProductsData.push({});
        renderProducts();
        productEntriesGrid.scrollTop = productEntriesGrid.scrollHeight;
    });

    addExpenseBtn.addEventListener('click', () => {
        allExpensesData.push({});
        renderExpenses();
        expenseEntriesGrid.scrollTop = expenseEntriesGrid.scrollHeight;
    });

    document.addEventListener('input', (e) => {
        if (e.target.closest('.product-entry')) {
            allProductsData = collectAllProductInputs(productEntriesGrid);
            updateTotalSales();
        } else if (e.target.closest('.expense-entry')) {
            allExpensesData = collectAllExpenseInputs(expenseEntriesGrid);
        }
        if (e.target.closest('.product-entry, .expense-entry, #companyName')) {
            saveDataToSession();
        }
    });

    document.addEventListener('focusout', (e) => {
        if (e.target.classList.contains('number-input')) {
            e.target.value = formatNumber(parseFormattedNumber(e.target.value));
        }
    });

    saveDataBtn.addEventListener('click', saveDataToSession);

    saveAndContinueBtn.addEventListener('click', async () => {
        await saveDataToSession();
        window.location.href = pageData.continue_url;
    });

    document.addEventListener('click', (e) => {
        const removeAndUpdate = (selector, dataArray, renderFunc) => {
            const entryToRemove = e.target.closest(selector);
            if (entryToRemove) {
                const indexToRemove = Array.from(entryToRemove.parentElement.children).indexOf(entryToRemove);
                dataArray.splice(indexToRemove, 1);
                saveDataToSession();
                renderFunc();
            }
        };
        if (e.target.classList.contains('remove-product-btn')) {
            removeAndUpdate('.product-entry', allProductsData, renderProducts);
        } else if (e.target.classList.contains('remove-expense-btn')) {
            removeAndUpdate('.expense-entry', allExpensesData, renderExpenses);
        }
    });

    // Initial render
    renderProducts();
    renderExpenses();
});