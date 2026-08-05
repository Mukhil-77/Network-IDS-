# Self-signing nginx reverse proxy - generates a self-signed TLS cert on
# startup (for development/demo; replace with real certs in production).

FROM nginx:1.27-alpine

RUN apk add --no-cache openssl

COPY deployment/nginx/nginx.conf /etc/nginx/nginx.conf

# Generate a self-signed certificate on first boot, then start nginx.
CMD ["sh", "-c", "\
    if [ ! -f /etc/nginx/ssl/server.crt ]; then \
        mkdir -p /etc/nginx/ssl && \
        openssl req -x509 -nodes -newkey rsa:2048 -days 365 \
          -keyout /etc/nginx/ssl/server.key -out /etc/nginx/ssl/server.crt \
          -subj '/CN=soc-platform' ; \
    fi && \
    nginx -g 'daemon off;'"]
