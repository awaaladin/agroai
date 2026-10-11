import './styles/main.css';
import { installRipple } from './ui/components/ripple.js';
import { route, startRouter, setGuard, go } from './router.js';
import { mountShell, inApp } from './ui/shell.js';
import { isLoggedIn } from './api/auth.js';
import './state/store.js';

// Routes are lazy: each screen is its own chunk, loaded only when visited.
route('/', () => import('./screens/landing.js'));
route('/login', () => import('./screens/login.js'));
route('/register', () => import('./screens/register.js'));
route('/dashboard', () => import('./screens/dashboard.js'));
route('/check', () => import('./screens/crop-check.js'));
route('/analyzing', () => import('./screens/analyzing.js'));
route('/result', () => import('./screens/result.js'));
route('/chat', () => import('./screens/chat.js'));
route('/weather', () => import('./screens/weather.js'));
route('/account', () => import('./screens/account.js'));
route('*', () => import('./screens/landing.js'));

// Public pages anyone can open; everything else needs an account or "continue as a guest".
const PUBLIC = new Set(['/', '/login', '/register']);
setGuard((path) => (PUBLIC.has(path) || inApp() ? null : '/'));

installRipple();
mountShell();

// Offline banner: a polite live region, not an error page.
const live = document.getElementById('live');
window.addEventListener('offline', () => { live.textContent = 'You are offline. Checking crops needs the internet.'; });
window.addEventListener('online', () => { live.textContent = 'You are back online.'; });

if (!location.hash) go('/', { replace: true });
startRouter(document.getElementById('main'));
void isLoggedIn;
