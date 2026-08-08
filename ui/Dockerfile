# The frontend is a static bundle. Node builds it, nginx serves it and proxies /api to
# the backend, so the browser talks to a single origin and there is one URL to open.

FROM node:20-alpine AS build
WORKDIR /ui

COPY package.json package-lock.json ./
RUN npm ci

COPY . .
RUN npm run build

FROM nginx:1.27-alpine
COPY --from=build /ui/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
