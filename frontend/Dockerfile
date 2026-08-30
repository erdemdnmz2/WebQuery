# Build stage
FROM node:24-alpine AS build

WORKDIR /app

# The lockfile is required, not optional: `npm ci` installs exactly the tree
# CI resolved and audited. `npm install` re-resolved every caret range at
# image build time, so the image could ship dependency versions no CI run
# ever saw — including ones an advisory fix had just moved past.
COPY package.json package-lock.json ./

RUN npm ci

COPY . .

RUN npm run build

# Production stage
FROM nginx:alpine

COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
