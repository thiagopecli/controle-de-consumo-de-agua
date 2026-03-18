// Main JavaScript file
console.log('Sistema de Controle de Consumo de Água carregado');

document.addEventListener('DOMContentLoaded', function() {
    document.documentElement.classList.add('js');
    const navToggle = document.querySelector('.nav-toggle');
    const navMenu = document.querySelector('.nav-menu');
    const navClose = document.querySelector('.nav-close');

    if (navToggle && navMenu) {
        navToggle.addEventListener('click', function() {
            const isOpen = navMenu.classList.toggle('is-open');
            navToggle.classList.toggle('is-hidden', isOpen);
            navToggle.setAttribute('aria-expanded', isOpen ? 'true' : 'false');
            navToggle.setAttribute('aria-label', isOpen ? 'Fechar menu' : 'Abrir menu');
            const toggleText = navToggle.querySelector('.nav-toggle-text');
            if (toggleText) {
                const openText = navToggle.getAttribute('data-open-text') || 'Fechar';
                const closeText = navToggle.getAttribute('data-close-text') || 'Menu';
                toggleText.textContent = isOpen ? openText : closeText;
            }
        });

        navMenu.addEventListener('click', function(event) {
            const target = event.target;
            if (target && target.closest('a')) {
                navMenu.classList.remove('is-open');
                navToggle.classList.remove('is-hidden');
                navToggle.setAttribute('aria-expanded', 'false');
                navToggle.setAttribute('aria-label', 'Abrir menu');
                const toggleText = navToggle.querySelector('.nav-toggle-text');
                if (toggleText) {
                    const closeText = navToggle.getAttribute('data-close-text') || 'Menu';
                    toggleText.textContent = closeText;
                }
            }
        });

        if (navClose) {
            navClose.addEventListener('click', function() {
                navMenu.classList.remove('is-open');
                navToggle.classList.remove('is-hidden');
                navToggle.setAttribute('aria-expanded', 'false');
                navToggle.setAttribute('aria-label', 'Abrir menu');
                const toggleText = navToggle.querySelector('.nav-toggle-text');
                if (toggleText) {
                    const closeText = navToggle.getAttribute('data-close-text') || 'Menu';
                    toggleText.textContent = closeText;
                }
            });
        }

        window.addEventListener('resize', function() {
            if (window.innerWidth > 768) {
                navMenu.classList.remove('is-open');
                navToggle.classList.remove('is-hidden');
                navToggle.setAttribute('aria-expanded', 'false');
                navToggle.setAttribute('aria-label', 'Abrir menu');
                const toggleText = navToggle.querySelector('.nav-toggle-text');
                if (toggleText) {
                    const closeText = navToggle.getAttribute('data-close-text') || 'Menu';
                    toggleText.textContent = closeText;
                }
            }
        });
    }
});

// Funções auxiliares
function formatarData(data) {
    return new Date(data).toLocaleDateString('pt-BR');
}

function formatarDataHora(data) {
    return new Date(data).toLocaleString('pt-BR');
}

function formatarNumero(numero, casasDecimais = 3) {
    return parseFloat(numero).toFixed(casasDecimais);
}

// Exportar funções
window.formatarData = formatarData;
window.formatarDataHora = formatarDataHora;
window.formatarNumero = formatarNumero;

if ('serviceWorker' in navigator) {
    let waitingWorker = null;
    let refreshing = false;

    function getAppVersion() {
        const appVersionMeta = document.querySelector('meta[name="app-version"]');
        return appVersionMeta ? appVersionMeta.getAttribute('content') : '1.0.0';
    }

    function showUpdateBanner() {
        const updateBanner = document.getElementById('updateBanner');
        const updateButton = document.getElementById('updateAppButton');

        if (!updateBanner || !updateButton) {
            return;
        }

        updateBanner.hidden = false;
        updateButton.onclick = function() {
            if (waitingWorker) {
                waitingWorker.postMessage({ type: 'SKIP_WAITING' });
            }
        };
    }

    function monitorNewServiceWorker(registration) {
        if (!registration) {
            return;
        }

        if (registration.waiting) {
            waitingWorker = registration.waiting;
            showUpdateBanner();
            return;
        }

        registration.addEventListener('updatefound', function() {
            const installingWorker = registration.installing;
            if (!installingWorker) {
                return;
            }

            installingWorker.addEventListener('statechange', function() {
                if (installingWorker.state === 'installed' && navigator.serviceWorker.controller) {
                    waitingWorker = installingWorker;
                    showUpdateBanner();
                }
            });
        });
    }

    window.addEventListener('load', function() {
        const appVersion = encodeURIComponent(getAppVersion());
        navigator.serviceWorker.register(`/service-worker.js?v=${appVersion}`).then(function(registration) {
            monitorNewServiceWorker(registration);

            setInterval(function() {
                registration.update();
            }, 60000);
        }).catch(function(error) {
            console.warn('Falha ao registrar service worker:', error);
        });

        navigator.serviceWorker.addEventListener('controllerchange', function() {
            if (refreshing) {
                return;
            }

            refreshing = true;
            window.location.reload();
        });
    });
}
