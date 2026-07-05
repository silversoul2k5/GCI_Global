// Thin fetch wrapper. Every function takes apiBase explicitly rather than
// importing a constant, since the user can change the API URL at runtime
// from the Settings tab — nothing here should ever cache a stale base URL.

async function request(apiBase, path, options = {}) {
  const url = `${apiBase.replace(/\/$/, '')}${path}`;
  let res;
  try {
    res = await fetch(url, {
      headers: { 'Content-Type': 'application/json' },
      ...options,
    });
  } catch (e) {
    throw new Error(
      `Could not reach ${apiBase}. Check that the backend is running and that your phone is on the same wifi as your computer.`
    );
  }
  if (!res.ok) {
    const text = await res.text().catch(() => '');
    throw new Error(`Server error ${res.status}: ${text || res.statusText}`);
  }
  return res.json();
}

export function fetchCustomer(apiBase, customerId) {
  return request(apiBase, `/customers/${customerId}`);
}

export function fetchOffersForCustomer(apiBase, customerId) {
  return request(apiBase, `/offers/customer/${customerId}`);
}

export function redeemOffer(apiBase, offerId) {
  return request(apiBase, `/offers/${offerId}/redeem`, { method: 'POST' });
}

export function fetchDemoCustomers(apiBase, limit = 5) {
  return request(apiBase, `/customers?risk_band=high&limit=${limit}`);
}

export function checkHealth(apiBase) {
  return request(apiBase, '/health');
}
