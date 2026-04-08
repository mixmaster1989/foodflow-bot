import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import vkBridge from '@vkontakte/vk-bridge'
import './index.css'
import App from './App.tsx'

// Initialize VK Bridge
vkBridge.send('VKWebAppInit');

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
)

