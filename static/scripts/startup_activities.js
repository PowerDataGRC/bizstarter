document.addEventListener('DOMContentLoaded', function () {
    const tableBody = document.querySelector('#activities-table tbody');
    if (!tableBody) return;

    const addRowBtn = document.getElementById('add-row-btn');
    const totalWeightBadge = document.getElementById('total-weight-badge');

    /**
     * Creates and appends a new activity row to the table.
     */
    function createRow() {
        const newRow = document.createElement('tr');
        newRow.innerHTML = `
        <td>
            <input type="hidden" name="id" value="">
            <input type="text" name="activity" class="form-control" required title="">
        </td>
        <td><input type="text" name="description" class="form-control" title=""></td>
        <td><input type="number" name="weight" class="form-control weight-input" value="0" min="0" max="100" required></td>
        <td>
            <div class="d-flex align-items-center">
                <input type="range" name="progress" class="form-range progress-slider" min="0" max="100" step="1" value="0">
                <span class="ms-2 progress-value fw-bold">0%</span>
            </div>
        </td>
        <td class="text-center">
            <i class="bi bi-trash-fill text-danger remove-row-btn" style="cursor: pointer; font-size: 1.2rem;" title="Remove item"></i>
        </td>
    `;
        tableBody.appendChild(newRow);
        attachEventListeners(newRow);
        updateTotalWeight(); // Update total when a new row with weight 0 is added
    }

    /**
     * Removes a table row and updates the total weight.
     * @param {HTMLElement} button - The remove button that was clicked.
     */
    function removeRow(button) {
        button.closest('tr').remove();
        updateTotalWeight();
    }

    /**
     * Calculates the total weight from all weight inputs and updates the badge.
     */
    function updateTotalWeight() {
        let total = 0;
        document.querySelectorAll('.weight-input').forEach(input => {
            const value = parseInt(input.value, 10);
            if (!isNaN(value)) {
                total += value;
            }
        });
        totalWeightBadge.textContent = `Total Weight: ${total}%`;
        totalWeightBadge.classList.toggle('bg-danger', total > 100);
        totalWeightBadge.classList.toggle('bg-primary', total <= 100);
    }

    /**
     * Attaches event listeners to elements within a given container (e.g., a new row).
     * @param {HTMLElement} element - The container element.
     */
    function attachEventListeners(element) {
        element.querySelectorAll('.remove-row-btn').forEach(btn => {
            btn.addEventListener('click', () => removeRow(btn));
        });
        element.querySelectorAll('.weight-input').forEach(input => {
            input.addEventListener('input', updateTotalWeight);
        });
        element.querySelectorAll('.progress-slider').forEach(slider => {
            slider.addEventListener('input', () => slider.nextElementSibling.textContent = `${slider.value}%`);
        });
        element.querySelectorAll('input[name="activity"], input[name="description"]').forEach(input => {
            input.addEventListener('input', () => input.title = input.value);
        });
    }

    if (addRowBtn) {
        addRowBtn.addEventListener('click', createRow);
    }

    attachEventListeners(document.body);
});