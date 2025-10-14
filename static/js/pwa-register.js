// PWA Registration Script for English Course
console.log('[PWA] Initializing PWA features...');

// Check if service workers are supported
if ('serviceWorker' in navigator) {
  // Wait for page to load
  window.addEventListener('load', () => {
    registerServiceWorker();
  });
}

// Register service worker
async function registerServiceWorker() {
  try {
    const registration = await navigator.serviceWorker.register('/sw.js', {
      scope: '/'
    });

    console.log('[PWA] Service Worker registered successfully:', registration.scope);

    // Check for updates
    registration.addEventListener('updatefound', () => {
      const newWorker = registration.installing;
      console.log('[PWA] New Service Worker found, installing...');

      newWorker.addEventListener('statechange', () => {
        if (newWorker.state === 'installed' && navigator.serviceWorker.controller) {
          // New service worker available
          console.log('[PWA] New version available! Please refresh.');
          showUpdateNotification();
        }
      });
    });

  } catch (error) {
    console.error('[PWA] Service Worker registration failed:', error);
  }
}

// Show update notification
function showUpdateNotification() {
  const notification = document.createElement('div');
  notification.id = 'pwa-update-notification';
  notification.style.cssText = `
    position: fixed;
    bottom: 20px;
    left: 50%;
    transform: translateX(-50%);
    background: #0d6efd;
    color: white;
    padding: 15px 25px;
    border-radius: 8px;
    box-shadow: 0 4px 12px rgba(0,0,0,0.15);
    z-index: 10000;
    display: flex;
    gap: 15px;
    align-items: center;
    animation: slideUp 0.3s ease-out;
  `;

  notification.innerHTML = `
    <span>New version available!</span>
    <button id="pwa-reload-btn" style="
      background: white;
      color: #0d6efd;
      border: none;
      padding: 5px 15px;
      border-radius: 4px;
      cursor: pointer;
      font-weight: bold;
    ">Reload</button>
    <button id="pwa-dismiss-btn" style="
      background: transparent;
      color: white;
      border: 1px solid white;
      padding: 5px 15px;
      border-radius: 4px;
      cursor: pointer;
    ">Later</button>
  `;

  document.body.appendChild(notification);

  document.getElementById('pwa-reload-btn').addEventListener('click', () => {
    window.location.reload();
  });

  document.getElementById('pwa-dismiss-btn').addEventListener('click', () => {
    notification.remove();
  });
}

// Add CSS animation
const style = document.createElement('style');
style.textContent = `
  @keyframes slideUp {
    from {
      transform: translateX(-50%) translateY(100px);
      opacity: 0;
    }
    to {
      transform: translateX(-50%) translateY(0);
      opacity: 1;
    }
  }
`;
document.head.appendChild(style);

// Install prompt handler
let deferredPrompt;

window.addEventListener('beforeinstallprompt', (e) => {
  console.log('[PWA] Install prompt available');
  // Prevent the mini-infobar from appearing on mobile
  e.preventDefault();
  // Stash the event so it can be triggered later
  deferredPrompt = e;
  // Show custom install button
  showInstallPromotion();
});

// Show install promotion
function showInstallPromotion() {
  const installBtn = document.createElement('button');
  installBtn.id = 'pwa-install-btn';
  installBtn.textContent = '📱 Install App';
  installBtn.style.cssText = `
    position: fixed;
    bottom: 20px;
    right: 20px;
    background: #28a745;
    color: white;
    border: none;
    padding: 12px 24px;
    border-radius: 25px;
    cursor: pointer;
    font-weight: bold;
    box-shadow: 0 4px 12px rgba(0,0,0,0.15);
    z-index: 9999;
    animation: pulse 2s infinite;
  `;

  installBtn.addEventListener('click', async () => {
    if (!deferredPrompt) {
      return;
    }

    // Show the install prompt
    deferredPrompt.prompt();

    // Wait for the user to respond to the prompt
    const { outcome } = await deferredPrompt.userChoice;
    console.log(`[PWA] User response to install prompt: ${outcome}`);

    // Clear the deferredPrompt
    deferredPrompt = null;

    // Remove the install button
    installBtn.remove();
  });

  document.body.appendChild(installBtn);

  // Add pulse animation
  const pulseStyle = document.createElement('style');
  pulseStyle.textContent = `
    @keyframes pulse {
      0% {
        box-shadow: 0 4px 12px rgba(40, 167, 69, 0.4);
      }
      50% {
        box-shadow: 0 4px 20px rgba(40, 167, 69, 0.8);
      }
      100% {
        box-shadow: 0 4px 12px rgba(40, 167, 69, 0.4);
      }
    }
  `;
  document.head.appendChild(pulseStyle);
}

// Track app install
window.addEventListener('appinstalled', () => {
  console.log('[PWA] App installed successfully!');
  // Hide the install promotion
  const installBtn = document.getElementById('pwa-install-btn');
  if (installBtn) {
    installBtn.remove();
  }
  // Track the installation
  trackInstallation();
});

// Track installation analytics (customize as needed)
function trackInstallation() {
  // Add your analytics tracking here
  console.log('[PWA] Tracking app installation...');
}

// Check if app is running as PWA
function isPWA() {
  return window.matchMedia('(display-mode: standalone)').matches ||
         window.navigator.standalone === true;
}

if (isPWA()) {
  console.log('[PWA] Running as installed PWA');
  document.body.classList.add('pwa-mode');
} else {
  console.log('[PWA] Running in browser');
}

// Online/Offline detection
window.addEventListener('online', () => {
  console.log('[PWA] Connection restored');
  showConnectionStatus('online');
});

window.addEventListener('offline', () => {
  console.log('[PWA] Connection lost - Working offline');
  showConnectionStatus('offline');
});

// Show connection status
function showConnectionStatus(status) {
  const existingStatus = document.getElementById('connection-status');
  if (existingStatus) {
    existingStatus.remove();
  }

  const statusBar = document.createElement('div');
  statusBar.id = 'connection-status';
  statusBar.style.cssText = `
    position: fixed;
    top: 0;
    left: 0;
    right: 0;
    padding: 10px;
    text-align: center;
    color: white;
    font-weight: bold;
    z-index: 10001;
    animation: slideDown 0.3s ease-out;
  `;

  if (status === 'online') {
    statusBar.style.background = '#28a745';
    statusBar.textContent = '✓ Back online';
    setTimeout(() => statusBar.remove(), 3000);
  } else {
    statusBar.style.background = '#dc3545';
    statusBar.textContent = '⚠ Working offline - Some features may be limited';
  }

  document.body.insertBefore(statusBar, document.body.firstChild);

  const slideStyle = document.createElement('style');
  slideStyle.textContent = `
    @keyframes slideDown {
      from {
        transform: translateY(-100%);
      }
      to {
        transform: translateY(0);
      }
    }
  `;
  document.head.appendChild(slideStyle);
}

console.log('[PWA] Setup complete!');
