/**
 * Parses a string that may contain commas as a floating-point number.
 * Includes error handling for unexpected input types.
 *
 * @param {string | number | any} input - The string or value to parse.
 * @param {number} defaultValue - The value to return if parsing fails. Defaults to 0.
 * @returns {number} The parsed number, or the default value if parsing is not possible.
 */
function parseFormattedNumber(input, defaultValue = 0) {
    // If it's already a valid number, return it directly.
    if (typeof input === 'number' && !isNaN(input)) {
        return input;
    }

    if (input === null || input === undefined) {
        return defaultValue;
    }

    try {
        const str = String(input).trim();
        if (str === '') return defaultValue;

        const number = parseFloat(str.replace(/,/g, ''));
        return isNaN(number) ? defaultValue : number;
    } catch (error) {
        console.error("Error in parseFormattedNumber:", error, "Input:", input);
        return defaultValue;
    }
}

/**
 * Formats a number into a string with commas as thousands separators.
 *
 * @param {string | number | null | undefined} num - The number to format.
 * @returns {string} The formatted number string, or an empty string if input is invalid.
 */
function formatNumber(num) {
    if (num === null || num === undefined || num === '') return '';
    const number = parseFloat(String(num).replace(/,/g, ''));
    return isNaN(number) ? '' : number.toLocaleString('en-US');
}

/**
 * Collects expense data from a container of form elements.
 * Assumes a specific structure for expense entries within the container.
 *
 * @param {HTMLElement} containerElement - The parent element containing the expense entries.
 * @returns {Array<Object>} An array of expense objects.
 */
function collectAllExpenseInputs(containerElement) {
    if (!containerElement) {
        console.error("Expense container element not provided to collectAllExpenseInputs.");
        return [];
    }

    const collectedData = [];
    const allEntryElements = containerElement.querySelectorAll('.expense-entry');

    allEntryElements.forEach(entry => {
        const itemInput = entry.querySelector('[name^="expense_item_"]');
        const amountInput = entry.querySelector('[name^="expense_amount_"]');
        const frequencyInput = entry.querySelector('[name^="expense_frequency_"]');

        const item = itemInput ? itemInput.value : '';
        const amount = amountInput ? parseFormattedNumber(amountInput.value) : 0;
        const frequency = frequencyInput ? frequencyInput.value : 'monthly';

        if (item || amount) {
            collectedData.push({
                item: item,
                amount: amount,
                frequency: frequency,
                readonly: itemInput ? itemInput.hasAttribute('readonly') : false
            });
        }
    });
    return collectedData;
}