# 3D garden built from the editor's layout (viewer/), with the original simple model at /jednoduchy/. Served by Caddy,
# which also forwards read-only /api/* requests to the editor container so the viewer can list and load layout versions.
FROM caddy:2-alpine
COPY deploy/viewer/Caddyfile /etc/caddy/Caddyfile
COPY viewer/index.html viewer/viewer.js viewer/walk.js viewer/navigation.mjs viewer/style.css viewer/layout-default.json /srv/
COPY viewer/assets/ /srv/assets/
COPY index.html /srv/jednoduchy/index.html
COPY verze/ /srv/verze/
RUN setcap -r /usr/bin/caddy
USER 1000:1000
EXPOSE 8080
