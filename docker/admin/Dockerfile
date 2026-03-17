FROM node:20-alpine

RUN apk add --no-cache bash git libc6-compat

ENV PNPM_HOME="/pnpm"
ENV PATH="$PNPM_HOME:$PATH"

RUN corepack enable

WORKDIR /workspace

CMD ["sh", "-lc", "if [ -f api/package.json ]; then pnpm install --no-frozen-lockfile && pnpm --filter api dev --host 0.0.0.0; else tail -f /dev/null; fi"]
