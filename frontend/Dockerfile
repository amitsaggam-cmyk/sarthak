# frontend/Dockerfile
FROM node:20-alpine

WORKDIR /app

# Install dependencies
COPY package*.json ./
RUN npm install

# Copy source code
COPY . .

# Build the React application for production
RUN npm run build

# Expose the Vite preview port
EXPOSE 5173

# Serve the built application using Vite preview
CMD ["npm", "run", "preview"]