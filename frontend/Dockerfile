# Use Node.js 20 as base image
FROM node:20-alpine

# Set working directory
WORKDIR /app

# Copy package files
COPY package*.json ./

# Install dependencies
RUN npm ci --only=production=false

# Copy source code
COPY . .

# Expose port
EXPOSE 4200

# Command to run the application in development mode
CMD ["npm", "start", "--", "--host", "0.0.0.0", "--port", "4200", "--poll", "2000"]
