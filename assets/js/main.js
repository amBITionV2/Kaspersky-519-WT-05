// Enhanced Theme Toggle Functionality
document.addEventListener('DOMContentLoaded', function() {
    const themeToggle = document.getElementById('themeToggle');
    const html = document.documentElement;

    // Check for saved theme preference or default to dark
    const currentTheme = localStorage.getItem('theme') || 'dark';

    // Apply the saved theme
    if (currentTheme === 'light') {
        html.setAttribute('data-theme', 'light');
    } else {
        html.removeAttribute('data-theme');
    }

    // Enhanced theme toggle functionality
    if (themeToggle) {
        themeToggle.addEventListener('click', function() {
            const currentTheme = html.getAttribute('data-theme');

            if (currentTheme === 'light') {
                // Switch to dark theme
                html.removeAttribute('data-theme');
                localStorage.setItem('theme', 'dark');
            } else {
                // Switch to light theme
                html.setAttribute('data-theme', 'light');
                localStorage.setItem('theme', 'light');
            }

            // Add enhanced animation effect
            themeToggle.style.transform = 'scale(0.95)';
            setTimeout(() => {
                themeToggle.style.transform = 'scale(1)';
            }, 150);
        });
    }

    // Mobile menu toggle functionality (existing)
    const hamburger = document.querySelector('.hamburger');
    const navLinks = document.querySelector('.nav-links');

    if (hamburger && navLinks) {
        hamburger.addEventListener('click', function() {
            navLinks.classList.toggle('open');
        });

        // Close mobile menu when clicking outside
        document.addEventListener('click', function(event) {
            if (!hamburger.contains(event.target) && !navLinks.contains(event.target)) {
                navLinks.classList.remove('open');
            }
        });
    }
});

// Smooth scrolling for anchor links
document.querySelectorAll('a[href^="#"]').forEach(anchor => {
    anchor.addEventListener('click', function (e) {
        e.preventDefault();
        const target = document.querySelector(this.getAttribute('href'));
        if (target) {
            target.scrollIntoView({
                behavior: 'smooth',
                block: 'start'
            });
        }
    });
});

// Add loading animation for buttons
document.querySelectorAll('.btn').forEach(button => {
    button.addEventListener('click', function() {
        if (!this.classList.contains('loading')) {
            this.classList.add('loading');
            setTimeout(() => {
                this.classList.remove('loading');
            }, 2000);
        }
    });
});
