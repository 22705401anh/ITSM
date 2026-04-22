// Theme initialization script
// Placed in <head> to prevent flashing of unstyled content
(function() {
    function getStoredTheme() {
        return localStorage.getItem('theme');
    }

    function getPreferredTheme() {
        const storedTheme = getStoredTheme();
        if (storedTheme) {
            return storedTheme;
        }
        return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
    }

    function setTheme(theme) {
        if (theme === 'auto') {
            document.documentElement.setAttribute('data-bs-theme', (window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'));
        } else {
            document.documentElement.setAttribute('data-bs-theme', theme);
        }
    }

    setTheme(getPreferredTheme());

    // Make functions globally available
    window.themeUtils = {
        getStoredTheme,
        getPreferredTheme,
        setTheme,
        toggleTheme: function() {
            const current = document.documentElement.getAttribute('data-bs-theme');
            const next = current === 'dark' ? 'light' : 'dark';
            localStorage.setItem('theme', next);
            setTheme(next);
            updateThemeUI(next);
        }
    };
})();

// Function to update UI elements (like navbar icons) based on current theme
function updateThemeUI(theme) {
    // Update theme toggle icon in navbar if it exists
    const themeIcon = document.getElementById('themeToggleIcon');
    if (themeIcon) {
        if (theme === 'dark') {
            themeIcon.className = 'fas fa-sun';
        } else {
            themeIcon.className = 'fas fa-moon';
        }
    }
    
    // Update settings page select if it exists
    const themeSelect = document.getElementById('theme');
    if (themeSelect) {
        const storedTheme = localStorage.getItem('theme');
        if (storedTheme === 'dark' || storedTheme === 'light' || storedTheme === 'auto') {
            const options = Array.from(themeSelect.options);
            const opt = options.find(o => o.value.toLowerCase() === storedTheme);
            if (opt) opt.selected = true;
        }
    }
}

// Run UI updates on load
window.addEventListener('DOMContentLoaded', () => {
    updateThemeUI(document.documentElement.getAttribute('data-bs-theme'));
});
