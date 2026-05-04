document.addEventListener('DOMContentLoaded', () => {
    const langToggleBtn = document.getElementById('lang-toggle');
    let currentLang = 'zh'; // Default language

    // Function to update texts based on selected language
    const updateLanguage = () => {
        // Handle title specifically because it has nested HTML
        const titleEl = document.querySelector('.title');
        if (currentLang === 'zh') {
            titleEl.innerHTML = `拥有心跳的<br><span class="gradient-text">自主 AI 智能体</span>`;
        } else {
            titleEl.innerHTML = `The Proactive <span class="gradient-text">AI Agent</span><br>With a Beating Heart.`;
        }

        // Handle all elements with data-zh and data-en attributes
        document.querySelectorAll('[data-zh][data-en]').forEach(el => {
            el.textContent = currentLang === 'zh' ? el.getAttribute('data-zh') : el.getAttribute('data-en');
        });
    };

    // Toggle event listener
    langToggleBtn.addEventListener('click', () => {
        currentLang = currentLang === 'zh' ? 'en' : 'zh';
        updateLanguage();
    });

    // Initialize with default language
    updateLanguage();

    // Intersection Observer for subtle scroll animations
    const observer = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                entry.target.style.opacity = '1';
                entry.target.style.transform = 'translateY(0)';
            }
        });
    }, {
        threshold: 0.1
    });

    // Apply animation starting state to cards and timeline items
    document.querySelectorAll('.feature-card, .timeline-item').forEach(el => {
        el.style.opacity = '0';
        el.style.transform = 'translateY(20px)';
        el.style.transition = 'opacity 0.6s ease-out, transform 0.6s ease-out';
        observer.observe(el);
    });
});
