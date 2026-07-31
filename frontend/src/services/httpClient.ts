import axios from 'axios'

// Boundary prepared for a later API integration. This placeholder never sends
// a request during the current frontend-only phase.
export const httpClient = axios.create({
  baseURL: '/api',
  headers: {
    Accept: 'application/json',
  },
  timeout: 8_000,
})
