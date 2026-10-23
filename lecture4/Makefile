
.PHONY: all db-up db-create test

COMPOSE := docker compose -f docker-compose.yml
TEST_DB_URL := mysql+pymysql://root:root@127.0.0.1:3306/isolation_lab
PYTEST := ../.venv/bin/pytest

all: test

db-up:
	@if [ "$$($(COMPOSE) ps --status running -q mysql)" = "" ]; then \
		$(COMPOSE) up -d mysql; \
	else \
		echo "MySQL already running"; \
	fi
	@until $(COMPOSE) exec -T mysql mysqladmin ping -h 127.0.0.1 -uroot -proot --silent 2>/dev/null; do \
		sleep 2; \
	done

db-create: db-up
	@$(COMPOSE) exec -T mysql mysql -uroot -proot -e "CREATE DATABASE IF NOT EXISTS isolation_lab;"

test: db-create
	ISOLATION_TEST_DATABASE_URL='$(TEST_DB_URL)' $(PYTEST) -v tests/isolation
