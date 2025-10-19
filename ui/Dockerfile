# syntax=docker/dockerfile:1.6
FROM node:20.15.0-alpine AS ui-build
WORKDIR /app/ui
COPY ui/package.json ui/package-lock.json ./
ARG UI_BUILD_CACHE_BUSTER=0
RUN echo "cache_buster=$UI_BUILD_CACHE_BUSTER" && npm ci --include=dev
COPY ui/ .
# Show scripts & fail fast if missing
RUN node -e "const s=require('./package.json').scripts||{}; if(!s.build){console.error('ERROR: ui/package.json has no \"build\" script'); process.exit(1)}; console.log('UI scripts:', s)"
RUN npm run build

FROM nginx:1.27-alpine AS ui
# Known outputs (copy first one that exists)
RUN mkdir -p /usr/share/nginx/html
RUN --mount=from=ui-build,source=/app/ui,target=/build \
    cp -r /build/dist/* /usr/share/nginx/html/ 2>/dev/null || \
    cp -r /build/build/* /usr/share/nginx/html/ 2>/dev/null || \
    cp -r /build/out/* /usr/share/nginx/html/ 2>/dev/null || \
    (echo "No build output found in dist/, build/, or out/" && exit 1)

# Copy nginx configuration
COPY ui/nginx.conf /etc/nginx/conf.d/default.conf
