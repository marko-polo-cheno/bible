interface AppConfig {
  API_BASE_URL: string;
  NODE_ENV: 'development' | 'production';
  IS_DEV: boolean;
  IS_PROD: boolean;
}

const validateEnvironment = (): AppConfig => {
  const apiUrl = import.meta.env.VITE_API_URL;
  const nodeEnv = import.meta.env.MODE;
  
  // For production builds, we'll set the Railway URL directly
  const productionUrl = 'https://bible-production-d7b3.up.railway.app';
  
  const config = {
    API_BASE_URL: apiUrl || (import.meta.env.DEV ? 'http://localhost:8000' : productionUrl),
    NODE_ENV: nodeEnv as 'development' | 'production',
    IS_DEV: import.meta.env.DEV,
    IS_PROD: import.meta.env.PROD
  };
  
  console.log('Environment config:', {
    VITE_API_URL: apiUrl,
    MODE: nodeEnv,
    DEV: import.meta.env.DEV,
    PROD: import.meta.env.PROD,
    API_BASE_URL: config.API_BASE_URL
  });
  
  return config;
};

export const ENV = validateEnvironment();
