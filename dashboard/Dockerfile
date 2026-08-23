FROM nginx:alpine

# Replace the default site config with proxy-aware config
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Static dashboard page
COPY index.html /usr/share/nginx/html/index.html

EXPOSE 80

HEALTHCHECK --interval=30s --timeout=3s --retries=3 \
    CMD wget -q -O- http://localhost:80/ >/dev/null || exit 1
