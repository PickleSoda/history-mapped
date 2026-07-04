import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { registerSW } from 'virtual:pwa-register';
import { Providers } from './app/providers';
import { AppRoutes } from './app/router';
import './styles.css';

// Registration failure is non-fatal: the app runs exactly as without a SW.
registerSW({
  immediate: true,
  onRegisterError(error) {
    console.warn('[pwa] service worker registration failed', error);
  },
});

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <Providers>
      <AppRoutes />
    </Providers>
  </StrictMode>,
);
