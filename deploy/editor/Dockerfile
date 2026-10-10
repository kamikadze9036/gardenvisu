# Editor: static tools/editor/ + a small Python API that stores the shared layout on the /data volume.
FROM python:3.13-alpine
RUN adduser -D -H -u 1000 app && mkdir /data && chown 1000:1000 /data   # a new named volume inherits this owner
WORKDIR /app
COPY deploy/editor/server.py /app/server.py
COPY tools/editor/editor.html tools/editor/plan.js tools/editor/layout.js tools/editor/layout.json /app/static/
USER 1000:1000
EXPOSE 8080
CMD ["python", "-u", "/app/server.py"]
