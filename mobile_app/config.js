import AsyncStorage from '@react-native-async-storage/async-storage';
import { createContext, useCallback, useContext, useEffect, useState } from 'react';

// ---------------------------------------------------------------------
// IMPORTANT — read this if the app can't reach the backend:
//
// Expo Go runs on your PHONE, not on your computer. "localhost" on your
// phone means the phone itself, not your laptop, so it will never reach
// a FastAPI server running on your laptop's localhost.
//
// Instead, use your computer's LAN IP address (the one on your home
// wifi), e.g. "http://192.168.1.23:8000". Find it with:
//   Mac/Linux : ipconfig getifaddr en0        (or: ifconfig | grep inet)
//   Windows   : ipconfig                      (look for "IPv4 Address")
// Your phone and computer must be on the same wifi network.
//
// You can change this default below, or change it from within the app
// on the Settings tab (Home screen) — no rebuild needed either way.
// ---------------------------------------------------------------------
export const DEFAULT_API_BASE = 'http://172.25.9.166:8000';
export const COMMON_API_BASES = [
  DEFAULT_API_BASE,
  'http://192.168.1.23:8000',
  'http://192.168.0.10:8000',
  'http://192.168.0.1:8000',
  'http://10.0.0.2:8000',
  'http://localhost:8000',
];

const API_BASE_KEY = 'churn_demo_api_base';
const CUSTOMER_ID_KEY = 'churn_demo_customer_id';

// A few real high-risk customer IDs from the trained model, used as
// convenient demo accounts to "log in" as on the Home screen. The list
// is refreshed live from the backend when it's reachable (see
// fetchDemoCustomers in api.js); these are just the offline fallback.
export const FALLBACK_DEMO_CUSTOMER_IDS = [1057208, 1045980, 1042069, 1071203, 1009076];

const AppConfigContext = createContext(null);

export function AppConfigProvider({ children }) {
  const [apiBase, setApiBaseState] = useState(DEFAULT_API_BASE);
  const [customerId, setCustomerIdState] = useState(FALLBACK_DEMO_CUSTOMER_IDS[0]);
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    (async () => {
      try {
        const [savedBase, savedId] = await Promise.all([
          AsyncStorage.getItem(API_BASE_KEY),
          AsyncStorage.getItem(CUSTOMER_ID_KEY),
        ]);
        if (savedBase) setApiBaseState(savedBase);
        if (savedId) setCustomerIdState(Number(savedId));
      } catch (e) {
        // AsyncStorage unavailable for some reason — fall back to in-memory defaults silently.
      } finally {
        setLoaded(true);
      }
    })();
  }, []);

  const setApiBase = useCallback((value) => {
    setApiBaseState(value);
    AsyncStorage.setItem(API_BASE_KEY, value).catch(() => {});
  }, []);

  const setCustomerId = useCallback((value) => {
    setCustomerIdState(value);
    AsyncStorage.setItem(CUSTOMER_ID_KEY, String(value)).catch(() => {});
  }, []);

  return (
    <AppConfigContext.Provider value={{ apiBase, setApiBase, customerId, setCustomerId, loaded }}>
      {children}
    </AppConfigContext.Provider>
  );
}

export function useAppConfig() {
  const ctx = useContext(AppConfigContext);
  if (!ctx) throw new Error('useAppConfig must be used within AppConfigProvider');
  return ctx;
}
