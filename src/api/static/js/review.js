// Manual Review JavaScript

document.addEventListener('DOMContentLoaded', function() {
    const form = document.getElementById('review-form');
    const submitBtn = document.getElementById('submit-btn');
    const resultsSection = document.getElementById('results-section');
    const loadingSpinner = document.getElementById('loading-spinner');
    const resultsContent = document.getElementById('results-content');

    form.addEventListener('submit', function(e) {
        e.preventDefault();

        const repoName = document.getElementById('repo_name').value.trim();
        const prNumber = parseInt(document.getElementById('pr_number').value);

        if (!repoName || !prNumber) {
            showToast('Please fill in all fields', 'warning');
            return;
        }

        // Validate repo format
        if (!repoName.includes('/')) {
            showToast('Repository name must be in format: owner/repo', 'warning');
            return;
        }

        // Show loading state
        submitBtn.disabled = true;
        submitBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Analyzing...';

        resultsSection.style.display = 'block';
        loadingSpinner.style.display = 'block';
        resultsContent.style.display = 'none';

        // Make API call
        fetch('/api/v1/review/manual', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                repo_name: repoName,
                pr_number: prNumber
            })
        })
        .then(response => {
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }
            return response.json();
        })
        .then(data => {
            displayResults(data);
        })
        .catch(error => {
            console.error('Error:', error);
            showError('Failed to complete review: ' + error.message);
        })
        .finally(() => {
            submitBtn.disabled = false;
            submitBtn.innerHTML = '<i class="fas fa-play"></i> Start Review';
        });
    });
});

function displayResults(data) {
    const loadingSpinner = document.getElementById('loading-spinner');
    const resultsContent = document.getElementById('results-content');
    const summary = document.getElementById('summary');
    const suggestionsList = document.getElementById('suggestions-list');
    const processingTime = document.getElementById('processing-time');

    // Update processing time
    processingTime.textContent = `${data.processing_time_seconds}s`;

    // Update summary
    summary.innerHTML = `<i class="fas fa-check-circle"></i> ${data.summary}`;

    // Clear and populate suggestions
    suggestionsList.innerHTML = '';

    if (data.suggestions && data.suggestions.length > 0) {
        data.suggestions.forEach((suggestion, index) => {
            const suggestionCard = createSuggestionCard(suggestion, index + 1);
            suggestionsList.appendChild(suggestionCard);
        });
    } else {
        suggestionsList.innerHTML = '<div class="alert alert-info"><i class="fas fa-info-circle"></i> No suggestions found - code looks good!</div>';
    }

    // Show results
    loadingSpinner.style.display = 'none';
    resultsContent.style.display = 'block';
    resultsContent.classList.add('fade-in');

    // Scroll to results
    resultsSection.scrollIntoView({ behavior: 'smooth' });
}

function createSuggestionCard(suggestion, number) {
    const card = document.createElement('div');
    card.className = 'card mb-3';

    const severityClass = {
        'error': 'danger',
        'warning': 'warning',
        'info': 'info'
    }[suggestion.severity] || 'secondary';

    const categoryIcon = {
        'style': 'fas fa-palette',
        'bug': 'fas fa-bug',
        'performance': 'fas fa-tachometer-alt',
        'security': 'fas fa-shield-alt',
        'best_practice': 'fas fa-lightbulb'
    }[suggestion.category] || 'fas fa-code';

    card.innerHTML = `
        <div class="card-header d-flex justify-content-between align-items-center">
            <span class="badge bg-${severityClass}">${number}. ${suggestion.severity.toUpperCase()}</span>
            <small class="text-muted">
                <i class="${categoryIcon}"></i> ${suggestion.category.replace('_', ' ')}
                ${suggestion.confidence ? ` • ${Math.round(suggestion.confidence * 100)}% confidence` : ''}
            </small>
        </div>
        <div class="card-body">
            <p class="card-text">${suggestion.suggestion}</p>
            ${suggestion.line_number ? `<small class="text-muted">Line ${suggestion.line_number}</small>` : ''}
            ${suggestion.file_path ? `<br><small class="text-muted"><i class="fas fa-file"></i> ${suggestion.file_path}</small>` : ''}
        </div>
    `;

    return card;
}

function showError(message) {
    const loadingSpinner = document.getElementById('loading-spinner');
    const resultsContent = document.getElementById('results-content');

    loadingSpinner.style.display = 'none';
    resultsContent.style.display = 'block';

    document.getElementById('summary').innerHTML = `<i class="fas fa-exclamation-triangle"></i> ${message}`;
    document.getElementById('summary').className = 'alert alert-danger';
    document.getElementById('suggestions-list').innerHTML = '';
}

function showToast(message, type = 'info') {
    const toastContainer = document.createElement('div');
    toastContainer.className = 'toast-container position-fixed top-0 end-0 p-3';
    toastContainer.style.zIndex = '9999';

    const toast = document.createElement('div');
    toast.className = `toast align-items-center text-white bg-${type === 'success' ? 'success' : type === 'warning' ? 'warning' : type === 'error' ? 'danger' : 'info'} border-0`;
    toast.setAttribute('role', 'alert');

    toast.innerHTML = `
        <div class="d-flex">
            <div class="toast-body">${message}</div>
            <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast"></button>
        </div>
    `;

    toastContainer.appendChild(toast);
    document.body.appendChild(toastContainer);

    const bsToast = new bootstrap.Toast(toast);
    bsToast.show();

    toast.addEventListener('hidden.bs.toast', () => {
        document.body.removeChild(toastContainer);
    });
}