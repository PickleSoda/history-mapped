FROM postgis/postgis:16-3.5 AS pgvector-builder

ARG PGVECTOR_VERSION=v0.8.2

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential \
        ca-certificates \
        git \
        postgresql-server-dev-16 \
    && git clone --branch ${PGVECTOR_VERSION} --depth 1 https://github.com/pgvector/pgvector.git /tmp/pgvector \
    && cd /tmp/pgvector \
    && make clean \
    && make OPTFLAGS="" \
    && make install \
    && rm -rf /tmp/pgvector \
    && rm -rf /var/lib/apt/lists/*

FROM postgis/postgis:16-3.5

# Runtime image only gets pgvector artifacts from builder stage.
COPY --from=pgvector-builder /usr/lib/postgresql/16/lib/vector.so /usr/lib/postgresql/16/lib/vector.so
COPY --from=pgvector-builder /usr/lib/postgresql/16/lib/bitcode/vector /usr/lib/postgresql/16/lib/bitcode/vector
COPY --from=pgvector-builder /usr/lib/postgresql/16/lib/bitcode/vector.index.bc /usr/lib/postgresql/16/lib/bitcode/vector.index.bc
COPY --from=pgvector-builder /usr/share/postgresql/16/extension/vector.control /usr/share/postgresql/16/extension/vector.control
COPY --from=pgvector-builder /usr/share/postgresql/16/extension/vector--*.sql /usr/share/postgresql/16/extension/
