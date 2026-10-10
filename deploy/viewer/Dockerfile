# 3D model in the browser (Three.js, index.html) and the earlier versions, served by Caddy.
FROM caddy:2-alpine
COPY deploy/viewer/Caddyfile /etc/caddy/Caddyfile
COPY index.html /srv/index.html
COPY verze/ /srv/verze/
RUN setcap -r /usr/bin/caddy
USER 1000:1000
EXPOSE 8080
