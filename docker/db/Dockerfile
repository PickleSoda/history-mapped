FROM postgis/postgis:16-3.5

# pgvector is available as a Debian package in the PostgreSQL apt repo
# which is already configured in the postgis base image.
RUN apt-get update \
    && apt-get install -y --no-install-recommends postgresql-16-pgvector \
    && rm -rf /var/lib/apt/lists/*
