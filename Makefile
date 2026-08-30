# Compose shortcuts.
#
# docker-compose.dev.yml is deliberately not named .override.yml, so it is not
# loaded automatically and the bare `docker compose up` a deploy runs stays on
# the production-safe topology (OQ-2026-015). These targets keep the local
# command short without putting that default back.

DEV := docker compose -f docker-compose.yml -f docker-compose.dev.yml

.PHONY: up down build logs ps prod-config dev-config

## Local development: base + dev conveniences (bind mount, published ports).
up:
	$(DEV) up

build:
	$(DEV) build

down:
	$(DEV) down

logs:
	$(DEV) logs -f

ps:
	$(DEV) ps

## Print the resolved topology for each mode. `prod-config` is the one to read
## before a deploy: it must show no bind mount and no published db port.
prod-config:
	docker compose -f docker-compose.yml config

dev-config:
	$(DEV) config
