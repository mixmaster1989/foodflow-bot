import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import vkBridge from '@vkontakte/vk-bridge'
import './index.css'
import App from './App.tsx'
import { ToastProvider } from './components/Toast'

// Initialize VK Bridge
vkBridge.send('VKWebAppInit');

// Handle VK Theme (Scheme)
vkBridge.subscribe((e) => {
  if (e.detail.type === 'VKWebAppUpdateConfig') {
    const scheme = e.detail.data.scheme ? e.detail.data.scheme : 'client_light';
    if (scheme.includes('light')) {
      document.body.classList.add('light-theme');
    } else {
      document.body.classList.remove('light-theme');
    }
  }
});

// Initial detection via URL params (if Bridge event is missed)
const params = new URLSearchParams(window.location.search);
if (params.get('vk_platform') && params.get('vk_appearance') === 'light') {
  document.body.classList.add('light-theme');
}

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <ToastProvider>
      <App />
    </ToastProvider>
  </StrictMode>,
)
