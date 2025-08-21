import React, { createContext, useContext, ReactNode } from 'react';
import axios from 'axios';

// Extend the Window interface to include electronAPI
declare global {
  interface Window {
    electronAPI?: any;
  }
}

// Determine API base URL based on environment
const getApiBaseUrl = () => {
  // Check if we're in Electron
  if (typeof window !== 'undefined' && window.electronAPI) {
    return 'http://localhost:3001/api';
  }
  
  // For web builds, use relative path or localhost
  if (import.meta.env.DEV) {
    return 'http://localhost:3001/api';
  }
  
  // Production build - assume backend is on same host
  return 'http://localhost:3001/api';
};

const API_BASE_URL = getApiBaseUrl();

interface ApiContextType {
  api: axios.AxiosInstance;
}

const ApiContext = createContext<ApiContextType | undefined>(undefined);

// Configure axios instance
const api = axios.create({
  baseURL: API_BASE_URL,
  timeout: 60000, // Increased timeout for desktop app
  headers: {
    'Content-Type': 'application/json',
  },
});

// Request interceptor
api.interceptors.request.use(
  (config) => {
    if (process.env.NODE_ENV === 'development') {
      console.log(`Making ${config.method?.toUpperCase()} request to ${config.url}`);
    }
    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

// Response interceptor
api.interceptors.response.use(
  (response) => {
    return response;
  },
  (error) => {
    if (error.code === 'ECONNREFUSED') {
      console.error('Backend connection refused. Please ensure the application backend is running.');
    } else {
      console.error('API Error:', error.response?.data || error.message);
    }
    return Promise.reject(error);
  }
);

interface ApiProviderProps {
  children: ReactNode;
}

export const ApiProvider: React.FC<ApiProviderProps> = ({ children }) => {
  return (
    <ApiContext.Provider value={{ api }}>
      {children}
    </ApiContext.Provider>
  );
};

export const useApi = () => {
  const context = useContext(ApiContext);
  if (context === undefined) {
    throw new Error('useApi must be used within an ApiProvider');
  }
  return context;
};