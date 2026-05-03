FROM node:20-alpine

RUN apk add --no-cache bash git libc6-compat \
    php84 php84-cli php84-phar php84-mbstring php84-openssl php84-tokenizer php84-xml php84-curl php84-dom php84-pdo php84-pdo_pgsql \
    && ln -sf /usr/bin/php84 /usr/bin/php

ENV PNPM_HOME="/pnpm"
ENV PATH="$PNPM_HOME:$PATH"

RUN corepack enable

WORKDIR /workspace

CMD ["sh", "-lc", "pnpm install --no-frozen-lockfile && pnpm --filter @history-mapped/api dev"]
