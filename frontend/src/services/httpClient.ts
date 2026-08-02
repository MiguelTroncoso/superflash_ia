import axios from 'axios'

export const httpClient = axios.create({
  baseURL: '/',
  headers: {
    Accept: 'application/json',
  },
  timeout: 8_000,
})
