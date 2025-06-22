#!/bin/sh

# Generate environment configuration file
echo "Generating environment configuration..."

# Default values
BACKEND_URL=${BACKEND_URL:-http://localhost:8000}
API_URL=${API_URL:-http://localhost:8000/api}

echo "BACKEND_URL: $BACKEND_URL"
echo "API_URL: $API_URL"

# Generate the env.js file with actual environment variables in the nginx html directory
cat > /usr/share/nginx/html/assets/env.js << EOF
// This script will be loaded before the main application
// Generated at container startup with actual environment variables
(function(window) {
  window.env = window.env || {};
  
  window.env['BACKEND_URL'] = '${BACKEND_URL}';
  window.env['API_URL'] = '${API_URL}';
  
  console.log('Environment variables loaded:', window.env);
})(this);
EOF

echo "Environment configuration generated successfully."

# Start the application
exec "$@"
