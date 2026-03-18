FROM node:20-alpine

RUN apk add --no-cache bash git libc6-compat

ENV PNPM_HOME="/pnpm"
ENV PATH="$PNPM_HOME:$PATH"

RUN corepack enable

WORKDIR /workspace

CMD ["sh", "-lc", "pnpm install --no-frozen-lockfile && pnpm --filter @wikiglobe/api dev"]
