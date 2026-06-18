FROM node:22-alpine AS compilacao

WORKDIR /app
RUN corepack enable
COPY package.json pnpm-lock.yaml ./
RUN pnpm install --frozen-lockfile
COPY . .
ARG VITE_API_URL=http://localhost:8000
ENV VITE_API_URL=${VITE_API_URL}
RUN pnpm run build


FROM nginxinc/nginx-unprivileged:1.27-alpine AS producao

COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=compilacao /app/dist /usr/share/nginx/html
EXPOSE 8080
