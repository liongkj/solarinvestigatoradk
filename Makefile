.PHONY: help dev-frontend dev-backend dev docker-build docker-dev docker-down docker-logs

help:
	@echo "Available commands:"
	@echo ""
	@echo "Development:"
	@echo "  make dev-frontend    - Starts the frontend development server (Angular)"
	@echo "  make dev-backend     - Starts the backend development server (FastAPI)"
	@echo "  make dev             - Starts both frontend and backend development servers"
	@echo ""
	@echo "Docker Development:"
	@echo "  make docker-build    - Build all Docker services"
	@echo "  make docker-dev      - Start all services in development mode with Docker"
	@echo "  make docker-down     - Stop all Docker services"
	@echo "  make docker-logs     - View logs from all services"
	@echo ""
	@echo "Production:"
	@echo "  make prod-setup      - Set up production environment (.env.prod)"
	@echo "  make prod-build      - Build production Docker images"
	@echo "  make prod-up         - Start production services"
	@echo "  make prod-down       - Stop production services"
	@echo "  make prod-restart    - Restart production services"
	@echo "  make prod-logs       - View production logs"
	@echo "  make prod-status     - Check production service status"
	@echo ""
	@echo "Production commands:"
	@echo "  make prod-setup      - Set up the production environment"
	@echo "  make prod-build      - Build production Docker images"
	@echo "  make prod-up         - Start production services"
	@echo "  make prod-down       - Stop production services"
	@echo "  make prod-logs       - View production logs"
	@echo "  make prod-restart    - Restart production services"
	@echo "  make prod-status     - Check production service status"

dev-frontend:
	@echo "Starting frontend development server..."
	@cd frontend && npm run start

dev-backend:
	@echo "Starting backend development server..."
	cd backend && uv run uvicorn src.main:app --host 0.0.0.0 --port 8000 --reload

# Run frontend and backend concurrently
dev:
	@echo "Starting both frontend and backend development servers..."
	@make dev-frontend & make dev-backend

# Docker commands
docker-build:
	@echo "Building all Docker services..."
	@docker-compose build

docker-dev:
	@echo "Starting all services in development mode with Docker..."
	@docker-compose -f docker-compose.yml -f docker-compose.dev.yml up --build

docker-down:
	@echo "Stopping all Docker services..."
	@docker-compose down

docker-logs:
	@echo "Viewing logs from all services..."
	@docker-compose logs -f

# Production commands
.PHONY: prod-setup prod-up prod-down prod-logs prod-build prod-restart

prod-setup:
	@echo "Setting up production environment..."
	@if [ ! -f .env.prod ]; then \
		echo "Creating .env.prod from example..."; \
		cp .env.prod.example .env.prod; \
		echo "Please edit .env.prod with your actual values before deploying"; \
	else \
		echo ".env.prod already exists"; \
	fi

prod-build:
	@echo "Building production Docker images..."
	docker-compose -f docker-compose.prod.yml build

prod-up: prod-setup
	@echo "Starting production services..."
	docker-compose -f docker-compose.prod.yml --env-file .env.prod up -d

prod-down:
	@echo "Stopping production services..."
	docker-compose -f docker-compose.prod.yml down

prod-logs:
	@echo "Viewing production logs..."
	docker-compose -f docker-compose.prod.yml logs -f

prod-restart:
	@echo "Restarting production services..."
	docker-compose -f docker-compose.prod.yml restart

prod-status:
	@echo "Checking production service status..."
	docker-compose -f docker-compose.prod.yml ps