// Dashboard JavaScript

// Global chart instances
let reviewTrendsChart = null;
let issueDistributionChart = null;

// Theme management
let currentTheme = 'dark';

function toggleTheme() {
    const root = document.documentElement;
    const themeBtn = document.querySelector('button[onclick="toggleTheme()"]');

    if (currentTheme === 'dark') {
        // Switch to light theme
        root.setAttribute('data-theme', 'light');
        currentTheme = 'light';
        themeBtn.innerHTML = '<i class="fas fa-sun"></i>';
        localStorage.setItem('theme', 'light');
    } else {
        // Switch to dark theme
        root.removeAttribute('data-theme');
        currentTheme = 'dark';
        themeBtn.innerHTML = '<i class="fas fa-moon"></i>';
        localStorage.setItem('theme', 'dark');
    }

    // Update charts theme
    updateChartsTheme();
}

// Initialize charts
function initializeCharts() {
    const reviewTrendsCtx = document.getElementById('reviewTrendsChart');
    const issueDistributionCtx = document.getElementById('issueDistributionChart');

    if (reviewTrendsCtx) {
        reviewTrendsChart = new Chart(reviewTrendsCtx, {
            type: 'line',
            data: {
                labels: ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'],
                datasets: [{
                    label: 'Reviews',
                    data: [12, 19, 15, 25, 22, 30, 28],
                    borderColor: 'rgba(102, 126, 234, 1)',
                    backgroundColor: 'rgba(102, 126, 234, 0.1)',
                    borderWidth: 3,
                    fill: true,
                    tension: 0.4,
                    pointBackgroundColor: 'rgba(102, 126, 234, 1)',
                    pointBorderColor: '#fff',
                    pointBorderWidth: 2,
                    pointRadius: 6,
                    pointHoverRadius: 8
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        display: false
                    }
                },
                scales: {
                    y: {
                        beginAtZero: true,
                        grid: {
                            color: currentTheme === 'dark' ? 'rgba(255, 255, 255, 0.1)' : 'rgba(0, 0, 0, 0.1)'
                        },
                        ticks: {
                            color: currentTheme === 'dark' ? '#b8c5d6' : '#6c757d'
                        }
                    },
                    x: {
                        grid: {
                            color: currentTheme === 'dark' ? 'rgba(255, 255, 255, 0.1)' : 'rgba(0, 0, 0, 0.1)'
                        },
                        ticks: {
                            color: currentTheme === 'dark' ? '#b8c5d6' : '#6c757d'
                        }
                    }
                },
                animation: {
                    duration: 2000,
                    easing: 'easeInOutQuart'
                }
            }
        });
    }

    if (issueDistributionCtx) {
        issueDistributionChart = new Chart(issueDistributionCtx, {
            type: 'doughnut',
            data: {
                labels: ['Security', 'Performance', 'Code Quality', 'Best Practices', 'Documentation'],
                datasets: [{
                    data: [25, 20, 30, 15, 10],
                    backgroundColor: [
                        'rgba(255, 107, 107, 0.8)',
                        'rgba(250, 112, 154, 0.8)',
                        'rgba(102, 126, 234, 0.8)',
                        'rgba(79, 172, 254, 0.8)',
                        'rgba(67, 233, 123, 0.8)'
                    ],
                    borderColor: [
                        'rgba(255, 107, 107, 1)',
                        'rgba(250, 112, 154, 1)',
                        'rgba(102, 126, 234, 1)',
                        'rgba(79, 172, 254, 1)',
                        'rgba(67, 233, 123, 1)'
                    ],
                    borderWidth: 2,
                    hoverOffset: 10
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        position: 'bottom',
                        labels: {
                            color: currentTheme === 'dark' ? '#b8c5d6' : '#6c757d',
                            padding: 20,
                            usePointStyle: true
                        }
                    }
                },
                animation: {
                    animateScale: true,
                    animateRotate: true,
                    duration: 2000,
                    easing: 'easeInOutQuart'
                }
            }
        });
    }
}

function updateChartsTheme() {
    if (reviewTrendsChart) {
        reviewTrendsChart.options.scales.y.grid.color = currentTheme === 'dark' ? 'rgba(255, 255, 255, 0.1)' : 'rgba(0, 0, 0, 0.1)';
        reviewTrendsChart.options.scales.y.ticks.color = currentTheme === 'dark' ? '#b8c5d6' : '#6c757d';
        reviewTrendsChart.options.scales.x.grid.color = currentTheme === 'dark' ? 'rgba(255, 255, 255, 0.1)' : 'rgba(0, 0, 0, 0.1)';
        reviewTrendsChart.options.scales.x.ticks.color = currentTheme === 'dark' ? '#b8c5d6' : '#6c757d';
        reviewTrendsChart.update();
    }

    if (issueDistributionChart) {
        issueDistributionChart.options.plugins.legend.labels.color = currentTheme === 'dark' ? '#b8c5d6' : '#6c757d';
        issueDistributionChart.update();
    }
}

// Refresh stats function
function refreshStats() {
    const btn = document.getElementById('refresh-btn');
    if (!btn) {
        console.error('Refresh button not found');
        return;
    }
    const originalText = btn.innerHTML;

    btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Refreshing...';
    btn.disabled = true;

    fetch('/api/v1/stats')
        .then(response => response.json())
        .then(data => {
            // Update stats cards
            updateStatsDisplay(data);
            // Update charts with new data
            updateChartsData(data);
            showToast('Stats refreshed successfully', 'success');
        })
        .catch(error => {
            console.error('Error refreshing stats:', error);
            showToast('Failed to refresh stats', 'error');
        })
        .finally(() => {
            btn.innerHTML = originalText;
            btn.disabled = false;
        });
}

// Update stats display
function updateStatsDisplay(data) {
    // Update stats numbers with animation
    const stats = {
        'total-reviews': data.total_reviews || 0,
        'avg-time': (data.avg_processing_time || 0).toFixed(1),
        'active-models': data.active_models || 1,
        'vector-count': data.vector_count || 0
    };

    Object.keys(stats).forEach(key => {
        const element = document.getElementById(key);
        if (element) {
            animateNumber(element, parseFloat(element.textContent) || 0, stats[key]);
        }
    });
}

// Animate number changes
function animateNumber(element, from, to) {
    const duration = 1000;
    const start = Date.now();
    const isFloat = to % 1 !== 0;

    const animate = () => {
        const elapsed = Date.now() - start;
        const progress = Math.min(elapsed / duration, 1);
        const current = from + (to - from) * progress;

        element.textContent = isFloat ? current.toFixed(1) : Math.floor(current);

        if (progress < 1) {
            requestAnimationFrame(animate);
        }
    };

    animate();
}

// Update charts with new data
function updateChartsData(data) {
    if (reviewTrendsChart && data.review_trends) {
        reviewTrendsChart.data.datasets[0].data = data.review_trends;
        reviewTrendsChart.update();
    }

    if (issueDistributionChart && data.issue_distribution) {
        issueDistributionChart.data.datasets[0].data = data.issue_distribution;
        issueDistributionChart.update();
    }
}

// Change time range for charts
function changeTimeRange(range) {
    // This would fetch data for different time ranges
    console.log('Changing time range to:', range);
    // For now, just show a toast
    showToast(`Switched to ${range} view`, 'info');
}

// Toast notification function
function showToast(message, type = 'info') {
    const toastContainer = document.createElement('div');
    toastContainer.className = 'toast-container position-fixed top-0 end-0 p-3';
    toastContainer.style.zIndex = '9999';

    const toast = document.createElement('div');
    toast.className = `toast align-items-center text-white bg-${type === 'success' ? 'success' : type === 'error' ? 'danger' : 'info'} border-0`;
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

    // Remove toast container after animation
    toast.addEventListener('hidden.bs.toast', () => {
        document.body.removeChild(toastContainer);
    });
}

// Initialize dashboard
document.addEventListener('DOMContentLoaded', function() {
    // Load saved theme
    const savedTheme = localStorage.getItem('theme') || 'dark';
    if (savedTheme === 'light') {
        document.documentElement.setAttribute('data-theme', 'light');
        currentTheme = 'light';
        const themeBtn = document.querySelector('button[onclick="toggleTheme()"]');
        if (themeBtn) themeBtn.innerHTML = '<i class="fas fa-sun"></i>';
    }

    // Initialize charts
    initializeCharts();

    // Auto-refresh stats every 30 seconds
    setInterval(refreshStats, 30000);

    // Add loading states to buttons
    document.querySelectorAll('.btn').forEach(btn => {
        btn.addEventListener('click', function() {
            if (this.href && !this.href.includes('#')) {
                this.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Loading...';
            }
        });
    });

    // Add particle effect to background
    createParticles();

    // Add hover effects to cards
    addCardHoverEffects();
});

// Create animated particles for futuristic effect
function createParticles() {
    const particleContainer = document.createElement('div');
    particleContainer.className = 'particles';
    particleContainer.style.cssText = `
        position: fixed;
        top: 0;
        left: 0;
        width: 100%;
        height: 100%;
        pointer-events: none;
        z-index: -1;
    `;

    for (let i = 0; i < 50; i++) {
        const particle = document.createElement('div');
        particle.style.cssText = `
            position: absolute;
            width: 2px;
            height: 2px;
            background: rgba(102, 126, 234, 0.3);
            border-radius: 50%;
            left: ${Math.random() * 100}%;
            top: ${Math.random() * 100}%;
            animation: float ${Math.random() * 10 + 10}s linear infinite;
        `;
        particleContainer.appendChild(particle);
    }

    document.body.appendChild(particleContainer);
}

// Add hover effects to cards
function addCardHoverEffects() {
    document.querySelectorAll('.stats-card').forEach(card => {
        card.addEventListener('mouseenter', function() {
            this.style.transform = 'translateY(-15px) scale(1.05)';
            this.style.boxShadow = '0 25px 50px rgba(0, 0, 0, 0.5)';
        });

        card.addEventListener('mouseleave', function() {
            this.style.transform = 'translateY(0) scale(1)';
            this.style.boxShadow = '';
        });
    });
}

// Add floating animation for particles
const style = document.createElement('style');
style.textContent = `
    @keyframes float {
        0% { transform: translateY(0px) rotate(0deg); opacity: 0.3; }
        50% { opacity: 0.8; }
        100% { transform: translateY(-100vh) rotate(360deg); opacity: 0.3; }
    }
`;
document.head.appendChild(style);