
import { DatabaseInfo, User, Workspace } from '../types';

/**
 * Global fetch wrapper for authenticated requests.
 * Handles 401 Unauthorized by redirecting to login.
 */
export const authenticatedFetch = async (url: string, options: RequestInit = {}) => {
  try {
    const response = await fetch(url, {
      ...options,
      credentials: 'include'
    });
    
    if (response.status === 401) {
      // Token invalid or missing, redirect via hash routing
      if (!window.location.hash.includes('/login') && !window.location.hash.includes('/register')) {
        window.location.hash = '/login';
      }
      return null;
    }
    
    return response;
  } catch (error) {
    console.error('API Fetch Error:', error);
    throw error;
  }
};
