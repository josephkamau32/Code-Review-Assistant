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

    // Update processing time safely
    processingTime.textContent = `${data.processing_time_seconds}s`;

    // Update summary safely with textContent (SEC-01)
    summary.replaceChildren();
    const summaryIcon = document.createElement('i');
    summaryIcon.className = 'fas fa-check-circle me-1';
    summary.appendChild(summaryIcon);
    summary.appendChild(document.createTextNode(' ' + (data.summary || '')));

    // Clear and populate suggestions
    suggestionsList.replaceChildren();

    if (data.suggestions && data.suggestions.length > 0) {
        data.suggestions.forEach((suggestion, index) => {
            const suggestionCard = createSuggestionCard(suggestion, index + 1);
            suggestionsList.appendChild(suggestionCard);
        });
    } else {
        const noSuggestions = document.createElement('div');
        noSuggestions.className = 'alert alert-info';
        const infoIcon = document.createElement('i');
        infoIcon.className = 'fas fa-info-circle me-1';
        noSuggestions.appendChild(infoIcon);
        noSuggestions.appendChild(document.createTextNode(' No suggestions found - code looks good!'));
        suggestionsList.appendChild(noSuggestions);
    }

    // Show results
    loadingSpinner.style.display = 'none';
    resultsContent.style.display = 'block';
    resultsContent.classList.add('fade-in');

    // Scroll to results
    const resultsSection = document.getElementById('results-section');
    if (resultsSection) {
        resultsSection.scrollIntoView({ behavior: 'smooth' });
    }
}

function createSuggestionCard(suggestion, number) {
    const card = document.createElement('div');
    card.className = 'card mb-3';

    const severityClass = {
        'error': 'danger',
        'warning': 'warning',
        'info': 'info'
    }[suggestion.severity] || 'secondary';

    const categoryIconClass = {
        'style': 'fas fa-palette',
        'bug': 'fas fa-bug',
        'performance': 'fas fa-tachometer-alt',
        'security': 'fas fa-shield-alt',
        'best_practice': 'fas fa-lightbulb'
    }[suggestion.category] || 'fas fa-code';

    // Header container
    const header = document.createElement('div');
    header.className = 'card-header d-flex justify-content-between align-items-center';

    // Severity badge
    const badge = document.createElement('span');
    badge.className = `badge bg-${severityClass}`;
    badge.textContent = `${number}. ${(suggestion.severity || '').toUpperCase()}`;
    header.appendChild(badge);

    // Metadata small tag
    const meta = document.createElement('small');
    meta.className = 'text-muted';
    const categoryIcon = document.createElement('i');
    categoryIcon.className = categoryIconClass;
    meta.appendChild(categoryIcon);

    const categoryText = ' ' + (suggestion.category ? suggestion.category.replace('_', ' ') : '');
    const confidenceText = suggestion.confidence ? ` \u2022 ${Math.round(suggestion.confidence * 100)}% confidence` : '';
    meta.appendChild(document.createTextNode(categoryText + confidenceText));
    header.appendChild(meta);

    // Card Body
    const body = document.createElement('div');
    body.className = 'card-body';

    // Suggestion text (safe via textContent)
    const p = document.createElement('p');
    p.className = 'card-text';
    p.textContent = suggestion.suggestion || '';
    body.appendChild(p);

    // Line number info (if present)
    if (suggestion.line_number) {
        const lineInfo = document.createElement('small');
        lineInfo.className = 'text-muted d-block';
        lineInfo.textContent = `Line ${suggestion.line_number}`;
        body.appendChild(lineInfo);
    }

    // File path info (if present, safe via textContent)
    if (suggestion.file_path) {
        const fileInfo = document.createElement('small');
        fileInfo.className = 'text-muted d-block';
        const fileIcon = document.createElement('i');
        fileIcon.className = 'fas fa-file me-1';
        fileInfo.appendChild(fileIcon);
        fileInfo.appendChild(document.createTextNode(suggestion.file_path));
        body.appendChild(fileInfo);
    }

    card.appendChild(header);
    card.appendChild(body);
    return card;
}

function showError(message) {
    const loadingSpinner = document.getElementById('loading-spinner');
    const resultsContent = document.getElementById('results-content');

    loadingSpinner.style.display = 'none';
    resultsContent.style.display = 'block';

    const summary = document.getElementById('summary');
    summary.replaceChildren();
    const errorIcon = document.createElement('i');
    errorIcon.className = 'fas fa-exclamation-triangle me-1';
    summary.appendChild(errorIcon);
    summary.appendChild(document.createTextNode(' ' + message));
    summary.className = 'alert alert-danger';

    const suggestionsList = document.getElementById('suggestions-list');
    suggestionsList.replaceChildren();
}

function showToast(message, type = 'info') {
    const toastContainer = document.createElement('div');
    toastContainer.className = 'toast-container position-fixed top-0 end-0 p-3';
    toastContainer.style.zIndex = '9999';

    const bgClass = type === 'success' ? 'success' : type === 'warning' ? 'warning' : type === 'error' ? 'danger' : 'info';
    const toast = document.createElement('div');
    toast.className = `toast align-items-center text-white bg-${bgClass} border-0`;
    toast.setAttribute('role', 'alert');

    const flexDiv = document.createElement('div');
    flexDiv.className = 'd-flex';

    const toastBody = document.createElement('div');
    toastBody.className = 'toast-body';
    toastBody.textContent = message;

    const closeBtn = document.createElement('button');
    closeBtn.type = 'button';
    closeBtn.className = 'btn-close btn-close-white me-2 m-auto';
    closeBtn.setAttribute('data-bs-dismiss', 'toast');

    flexDiv.appendChild(toastBody);
    flexDiv.appendChild(closeBtn);
    toast.appendChild(flexDiv);

    toastContainer.appendChild(toast);
    document.body.appendChild(toastContainer);

    const bsToast = new bootstrap.Toast(toast);
    bsToast.show();

    toast.addEventListener('hidden.bs.toast', () => {
        if (toastContainer.parentNode) {
            document.body.removeChild(toastContainer);
        }
    });
}