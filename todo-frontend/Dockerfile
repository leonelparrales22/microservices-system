# Simple Dockerfile for serving pre-built React application
FROM nginx:alpine

# Copy pre-built application (build it locally first)
COPY build /usr/share/nginx/html

# Copy custom nginx configuration
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Expose port 80
EXPOSE 80

# Start nginx
CMD ["nginx", "-g", "daemon off;"]