# Build the static frontend, then serve it with nginx.
FROM node:20-alpine AS build
WORKDIR /app
COPY package.json package-lock.json ./
# npm install (not npm ci) until package-lock.json is regenerated once with the new devDependencies
RUN npm install --no-audit --no-fund
COPY . .
# Public URL of the API, baked in at build time (e.g. https://api.example.com)
ARG VITE_API_URL
ENV VITE_API_URL=${VITE_API_URL}
RUN npm run build

FROM nginx:1.27-alpine
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 80
