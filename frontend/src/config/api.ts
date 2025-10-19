import { ENV } from './env';

export const API_CONFIG = {
  BASE_URL: ENV.API_BASE_URL,
  ENDPOINTS: {
    SEARCH: '/search'
  }
} as const;
