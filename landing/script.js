/* ===== FoodFlow Landing — JS ===== */
document.addEventListener('DOMContentLoaded', () => {

    /* --- Intersection Observer for fade-in animations --- */
    const observer = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                entry.target.classList.add('visible');
                observer.unobserve(entry.target);
            }
        });
    }, { threshold: 0.1, rootMargin: '0px 0px -40px 0px' });

    document.querySelectorAll('.fade-up').forEach(el => observer.observe(el));

    /* --- Dashboard calorie ring animation --- */
    const dashObserver = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                // Animate macro bars
                setTimeout(() => {
                    document.querySelector('.macro-fill-p').style.width = '72%';
                    document.querySelector('.macro-fill-f').style.width = '58%';
                    document.querySelector('.macro-fill-c').style.width = '65%';
                    document.querySelector('.macro-fill-fi').style.width = '41%';
                }, 400);
                dashObserver.unobserve(entry.target);
            }
        });
    }, { threshold: 0.3 });

    const dashEl = document.querySelector('.dashboard-mockup');
    if (dashEl) dashObserver.observe(dashEl);

    /* --- FAQ Accordion --- */
    document.querySelectorAll('.faq-q').forEach(btn => {
        btn.addEventListener('click', () => {
            const item = btn.closest('.faq-item');
            const wasOpen = item.classList.contains('open');
            // Close all
            document.querySelectorAll('.faq-item').forEach(i => i.classList.remove('open'));
            // Toggle current
            if (!wasOpen) item.classList.add('open');
        });
    });

    /* --- Mobile Menu Toggle --- */
    const toggle = document.querySelector('.mobile-toggle');
    const mobileMenu = document.querySelector('.mobile-menu');
    if (toggle && mobileMenu) {
        toggle.addEventListener('click', () => {
            mobileMenu.classList.toggle('active');
            document.body.style.overflow = mobileMenu.classList.contains('active') ? 'hidden' : '';
        });
        mobileMenu.querySelectorAll('a').forEach(link => {
            link.addEventListener('click', () => {
                mobileMenu.classList.remove('active');
                document.body.style.overflow = '';
            });
        });
    }

    /* --- Smooth scroll for anchor links --- */
    document.querySelectorAll('a[href^="#"]').forEach(a => {
        a.addEventListener('click', e => {
            const target = document.querySelector(a.getAttribute('href'));
            if (target) {
                e.preventDefault();
                target.scrollIntoView({ behavior: 'smooth', block: 'start' });
            }
        });
    });

    /* --- Counter animation for social proof --- */
    const counterObserver = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                const el = entry.target;
                const target = parseInt(el.dataset.count, 10);
                const suffix = el.dataset.suffix || '';
                const prefix = el.dataset.prefix || '';
                let current = 0;
                const step = Math.max(1, Math.ceil(target / 60));
                const interval = setInterval(() => {
                    current += step;
                    if (current >= target) {
                        current = target;
                        clearInterval(interval);
                    }
                    el.textContent = prefix + current.toLocaleString('ru-RU') + suffix;
                }, 25);
                counterObserver.unobserve(el);
            }
        });
    }, { threshold: 0.5 });

    document.querySelectorAll('[data-count]').forEach(el => counterObserver.observe(el));

    /* --- Navbar background on scroll --- */
    const navbar = document.querySelector('.navbar');
    window.addEventListener('scroll', () => {
        if (window.scrollY > 50) {
            navbar.style.borderColor = 'rgba(255,255,255,0.12)';
        } else {
            navbar.style.borderColor = 'rgba(255,255,255,0.08)';
        }
    }, { passive: true });
});
