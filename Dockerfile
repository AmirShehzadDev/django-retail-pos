FROM node:22.22.0-alpine3.23 AS assets
WORKDIR /build
COPY package.json package-lock.json ./
RUN npm ci --ignore-scripts
COPY assets ./assets
COPY templates ./templates
COPY apps ./apps
COPY static/js ./static/js
RUN npm run css:build

FROM python:3.13.14-slim-bookworm AS runtime

ARG APP_VERSION=development
LABEL org.opencontainers.image.title="Single-Shop Retail POS" \
      org.opencontainers.image.version="${APP_VERSION}"

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DJANGO_SETTINGS_MODULE=config.settings.production \
    POS_APP_VERSION=${APP_VERSION} \
    PATH="/home/pos/.local/bin:${PATH}"

RUN groupadd --system pos && useradd --system --gid pos --create-home pos
WORKDIR /app

COPY requirements/base.txt requirements/base.txt
RUN pip install --no-cache-dir --disable-pip-version-check -r requirements/base.txt

COPY --chown=pos:pos manage.py ./
COPY --chown=pos:pos config ./config
COPY --chown=pos:pos apps ./apps
COPY --chown=pos:pos templates ./templates
COPY --chown=pos:pos static ./static
COPY --from=assets --chown=pos:pos /build/static/css/app.css ./static/css/app.css
COPY --chown=pos:pos docker/gunicorn.conf.py ./docker/gunicorn.conf.py

RUN mkdir -p /app/var/log /app/var/static && chown -R pos:pos /app/var

USER pos
RUN DJANGO_SECRET_KEY=build-only-secret-that-is-long-enough-1234567890 \
    DJANGO_ALLOWED_HOSTS=127.0.0.1 \
    POS_DB_NAME=build \
    POS_DB_USER=build \
    POS_DB_PASSWORD=build \
    python manage.py collectstatic --noinput

EXPOSE 8000
CMD ["gunicorn", "config.wsgi:application", "--config", "/app/docker/gunicorn.conf.py"]
