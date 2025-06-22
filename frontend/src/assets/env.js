// This script will be loaded before the main application
// Will be replaced with actual environment variables at container startup
(function(window) {
  window.env = window.env || {};
  
  // These will be replaced by docker-entrypoint.sh
  window.env['BACKEND_URL'] = 'http://localhost:8000';
  window.env['API_URL'] = 'http://localhost:8000/api';
  
  console.log('Environment variables loaded:', window.env);
})(this);
