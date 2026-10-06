FROM postgis/postgis:16-3.5 AS pgvector-builder

ARG PGVECTOR_VERSION=v0.8.2

# The base image is Debian bullseye, which is end-of-life: apt.postgresql.org
# (bullseye-pgdg) and deb.debian.org now return 404, and the packages live on
# apt-archive.postgresql.org and archive.debian.org. Only this build stage is
# repointed. The runtime stage keeps the stock base so prod's glibc and
# collations are unchanged.
RUN sed -i 's#apt.postgresql.org/pub/repos/apt#apt-archive.postgresql.org/pub/repos/apt#' \
        /etc/apt/sources.list.d/*.list \
    && sed -i -e 's#deb.debian.org#archive.debian.org#' -e '/bullseye-updates/d' /etc/apt/sources.list \
    && apt-get -o Acquire::Check-Valid-Until=false update \
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
