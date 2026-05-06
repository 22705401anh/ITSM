// Theme Toggle — Light (default) / Dark
// Runs in <head> to prevent flash of wrong theme
(function() {
    var stored = localStorage.getItem('itsm-theme');
    // Default is light
    var theme = (stored === 'dark') ? 'dark' : 'light';

    // Apply immediately to prevent flash
    if (theme === 'dark') {
        document.documentElement.classList.add('dark-theme');
    }
})();

// After DOM ready — wire up the toggle button and icon
document.addEventListener('DOMContentLoaded', function() {
    var isDark = document.documentElement.classList.contains('dark-theme');
    updateToggleIcon(isDark);

    var btn = document.getElementById('themeToggleBtn');
    if (btn) {
        btn.addEventListener('click', function() {
            var html = document.documentElement;
            html.classList.toggle('dark-theme');
            var nowDark = html.classList.contains('dark-theme');
            localStorage.setItem('itsm-theme', nowDark ? 'dark' : 'light');
            updateToggleIcon(nowDark);
        });
    }
});

function updateToggleIcon(isDark) {
    var icon = document.getElementById('themeToggleIcon');
    if (icon) {
        icon.className = isDark ? 'fas fa-sun' : 'fas fa-moon';
    }
}
