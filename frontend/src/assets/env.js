// This script will be loaded before the main application
// Generated at container startup with actual environment variables
(function(window) {
  window.env = window.env || {};
  
  window.env['BACKEND_URL'] = 'http://backend:8000';
  window.env['API_URL'] = 'http://backend:8000/api';
  
  console.log('Environment variables loaded:', window.env);
})(this);
