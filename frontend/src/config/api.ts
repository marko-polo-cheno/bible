import { ENV } from './env';

export const API_CONFIG = {
  BASE_URL: ENV.API_BASE_URL,
  ENDPOINTS: {
    SEARCH: '/search',
    TESTIMONIES_SEARCH: '/testimonies-search',
    TESTIMONIES_SUGGEST: '/testimonies-suggest',
  }
} as const;
