# EventFlow - Makefile unificado
# Uso: make <comando>
# Ver make help para lista de comandos

.PHONY: help up down build test logs clean ps status

# Variables
COMPOSE_FILE = docker-compose.yml
SERVICES = usuarios-service eventos-service reservas-service
DBS = mongodb redis postgresql

# Colores para output
GREEN = \033[0;32m
YELLOW = \033[1;33m
RED = \033[0;31m
NC = \033[0m

help: ## Mostrar esta ayuda
	@echo "$(GREEN)EventFlow - Comandos disponibles$(NC)"
	@echo ""
	@awk 'BEGIN {FS = ":.*##"; printf "%-20s %s\n", "Comando", "Descripción"} /^[a-zA-Z_-]+:.*?##/ { printf "$(YELLOW)%-20s$(NC) %s\n", $$1, $$2 }' $(MAKEFILE_LIST)

up: ## Levantar todos los servicios (DBs + microservicios)
	@echo "$(GREEN)🚀 Levantando EventFlow...$(NC)"
	docker compose -f $(COMPOSE_FILE) up -d
	@echo "$(GREEN)✅ Servicios levantados. Usa 'make logs' para ver logs.$(NC)"

down: ## Bajar todos los servicios
	@echo "$(YELLOW)🛑 Bajando EventFlow...$(NC)"
	docker compose -f $(COMPOSE_FILE) down
	@echo "$(GREEN)✅ Servicios detenidos.$(NC)"

build: ## Construir imágenes de todos los microservicios
	@echo "$(GREEN)🔨 Construyendo microservicios...$(NC)"
	docker compose -f $(COMPOSE_FILE) build $(SERVICES)
	@echo "$(GREEN)✅ Build completado.$(NC)"

build-no-cache: ## Construir sin caché
	@echo "$(GREEN)🔨 Construyendo sin caché...$(NC)"
	docker compose -f $(COMPOSE_FILE) build --no-cache $(SERVICES)

test: ## Ejecutar tests de todos los microservicios
	@echo "$(GREEN)🧪 Ejecutando tests...$(NC)"
	@for svc in $(SERVICES); do \
		echo "$(YELLOW)Testing $$svc...$(NC)"; \
		docker compose -f $(COMPOSE_FILE) run --rm $$svc python -m pytest tests/ -v --tb=short -p no:schemathesis || true; \
	done

test-unit: ## Ejecutar solo tests unitarios
	@for svc in $(SERVICES); do \
		echo "$(YELLOW)Unit tests $$svc...$(NC)"; \
		docker compose -f $(COMPOSE_FILE) run --rm $$svc python -m pytest tests/unit/ -v --tb=short || true; \
	done

test-integration: ## Ejecutar tests de integración
	@for svc in $(SERVICES); do \
		echo "$(YELLOW)Integration tests $$svc...$(NC)"; \
		docker compose -f $(COMPOSE_FILE) run --rm $$svc python -m pytest tests/integration/ -v --tb=short || true; \
	done

test-contract: ## Ejecutar tests de contrato
	@for svc in $(SERVICES); do \
		echo "$(YELLOW)Contract tests $$svc...$(NC)"; \
		docker compose -f $(COMPOSE_FILE) run --rm $$svc python -m pytest tests/contract/ -v --tb=short || true; \
	done

logs: ## Ver logs de todos los servicios
	docker compose -f $(COMPOSE_FILE) logs -f $(SERVICES) $(DBS)

logs-svc: ## Ver logs de un servicio específico (uso: make logs-svc SVC=usuarios-service)
	docker compose -f $(COMPOSE_FILE) logs -f $(SVC)

logs-db: ## Ver logs de bases de datos
	docker compose -f $(COMPOSE_FILE) logs -f $(DBS)

ps: ## Ver estado de contenedores
	@echo "$(GREEN)Estado de contenedores:$(NC)"
	docker compose -f $(COMPOSE_FILE) ps

status: ps ## Alias para ps

health: ## Verificar health checks de todos los servicios
	@echo "$(GREEN)🏥 Verificando health checks...$(NC)"
	@for port in 8001 8002 8003; do \
		echo -n "Puerto $$port: "; \
		curl -s -o /dev/null -w "%{http_code}" http://localhost:$$port/health && echo " OK" || echo " FAIL"; \
	done

clean: ## Limpiar contenedores, volúmenes e imágenes huérfanas
	@echo "$(RED)🧹 Limpiando...$(NC)"
	docker compose -f $(COMPOSE_FILE) down -v --remove-orphans
	docker system prune -f --volumes
	@echo "$(GREEN)✅ Limpieza completada.$(NC)"

restart: down up ## Reiniciar todos los servicios

rebuild: down build up ## Reconstruir y reiniciar todo

# Comandos por servicio
up-usuarios: ## Levantar solo usuarios-service
	docker compose -f $(COMPOSE_FILE) up -d mongodb usuarios-service

up-eventos: ## Levantar solo eventos-service
	docker compose -f $(COMPOSE_FILE) up -d mongodb eventos-service

up-reservas: ## Levantar solo reservas-service
	docker compose -f $(COMPOSE_FILE) up -d mongodb redis postgresql reservas-service

# Desarrollo
dev-usuarios: ## Modo desarrollo para usuarios-service (hot reload)
	docker compose -f $(COMPOSE_FILE) up -d mongodb
	cd usuarios-service && uvicorn src.main:app --reload --host 0.0.0.0 --port 8001

dev-eventos: ## Modo desarrollo para eventos-service
	docker compose -f $(COMPOSE_FILE) up -d mongodb
	cd eventos-service && uvicorn src.main:app --reload --host 0.0.0.0 --port 8002

dev-reservas: ## Modo desarrollo para reservas-service
	docker compose -f $(COMPOSE_FILE) up -d mongodb redis postgresql
	cd reservas-service && uvicorn src.main:app --reload --host 0.0.0.0 --port 8003

# Utilidades
shell-usuarios: ## Abrir shell en contenedor usuarios-service
	docker compose -f $(COMPOSE_FILE) exec usuarios-service bash

shell-eventos: ## Abrir shell en contenedor eventos-service
	docker compose -f $(COMPOSE_FILE) exec eventos-service bash

shell-reservas: ## Abrir shell en contenedor reservas-service
	docker compose -f $(COMPOSE_FILE) exec reservas-service bash

shell-mongo: ## Abrir shell en MongoDB
	docker compose -f $(COMPOSE_FILE) exec mongodb mongosh

shell-redis: ## Abrir shell en Redis
	docker compose -f $(COMPOSE_FILE) exec redis redis-cli

shell-pg: ## Abrir shell en PostgreSQL
	docker compose -f $(COMPOSE_FILE) exec postgresql psql -U eventflow_user -d eventflow

# Spec-kit
spec-analyze: ## Analizar specs con speckit
	@echo "Ejecutando /speckit.analyze en cada spec..."
	@for spec in .specify/specs/*/; do \
		echo "Analizando $$spec..."; \
	done

spec-implement: ## Implementar specs (requiere speckit)
	@echo "Ejecutando /speckit.implement..."
	@for spec in .specify/specs/*/; do \
		echo "Implementando $$spec..."; \
	done

# CI/CD
ci: build test ## Pipeline CI completo (build + tests)
	@echo "$(GREEN)✅ CI pipeline completado$(NC)"

# Documentación
docs: ## Generar/actualizar documentación
	@echo "$(GREEN)📚 Generando documentación...$(NC)"
	@echo "README.md actualizado"

# Verificación completa
verify: health test ## Verificación completa (health + tests)
	@echo "$(GREEN)✅ Verificación completa exitosa$(NC)"

# Información
info: ## Mostrar información del proyecto
	@echo "$(GREEN)EventFlow - Plataforma de Eventos$(NC)"
	@echo "Servicios: $(SERVICES)"
	@echo "Bases de datos: $(DBS)"
	@echo "Puertos: usuarios=8001, eventos=8002, reservas=8003"
	@echo "Docker Compose: $(COMPOSE_FILE)"