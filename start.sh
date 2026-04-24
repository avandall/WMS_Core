#!/bin/bash

# WMS Quick Start Script
# Usage: ./quick_start.sh [dev|prod|down]

set -e

# Đọc tham số truyền vào, mặc định là dev
MODE=${1:-dev}

# Xác định file environment sẽ sử dụng
ENV_FILE=".env.docker"
if [ ! -f $ENV_FILE ]; then 
    ENV_FILE=".env.dev"
    echo "⚠️  $ENV_FILE not found, falling back to .env.dev"
fi

case $MODE in
    "dev"|"development")
        echo "🚀 Starting WMS in DEVELOPMENT mode..."
        
        # Tạo file .env.docker nếu chưa có
        if [ ! -f .env.docker ]; then
            echo "📋 Creating .env.docker from .env.dev..."
            cp .env.dev .env.docker
        fi
        
        # Đảm bảo các biến quan trọng có trong file env để tránh Warning
        if ! grep -q "ENVIRONMENT=" .env.docker; then
            echo "ENVIRONMENT=development" >> .env.docker
            echo "AUTO_SEED_DATA=true" >> .env.docker
        fi
        
        # Khởi chạy kèm theo file env và profile dev (Adminer)
        docker compose --env-file .env.docker --profile dev up -d
        
        echo ""
        echo "✅ Development environment started!"
        echo "🌐 API:         http://localhost:8000"
        echo "🌐 Dashboard:   http://localhost:8080"
        echo "🌐 Adminer:     http://localhost:8090"
        echo ""
        echo "🔧 Add seed data, run: docker compose exec api python ./scripts/seed.py"
        ;;
        
    "prod"|"production")
        echo "🏭 Starting WMS in PRODUCTION mode with Cloudflare Tunnel..."
        
        # 1. Kiểm tra file env
        if [ ! -f .env.docker ]; then
            cp .env.prod .env.docker
            echo "⚠️  IMPORTANT: Edit .env.docker and add your TUNNEL_TOKEN!"
        fi
        
        # 2. Chạy cùng lúc profile mặc định và profile tunnel
        # Docker Compose cho phép gọi nhiều profile cùng lúc bằng cách lặp lại cờ --profile
        docker compose --env-file .env.docker --profile tunnel up -d
        
        echo "✅ Production environment and Tunnel started!"
        ;;
        
    "down"|"stop")
        echo "?? Stopping WMS while preserving database volumes..."
        # --profile "*" : T?t s?y m?i service thu?c b?t k? profile nào (adminer, v.v.)
        # --remove-orphans : Xóa các container ? không còn n?m trong file config
        # Không dùng -v : Gi? l?i các volume d? li?u
        docker compose --env-file .env.docker --profile "*" down --remove-orphans
        
        echo "?? System stopped. Database volumes preserved."
        ;;
        
    "down-clean"|"clean"|"reset")
        echo "?? Stopping WMS and cleaning up ALL resources including database..."
        # --profile "*" : T?t s?y m?i service thu?c b?t k? profile nào (adminer, v.v.)
        # --remove-orphans : Xóa các container ? không còn n?m trong file config
        # -v : Xóa các volume d? li?u (RESET DATABASE)
        docker compose --env-file .env.docker --profile "*" down -v --remove-orphans
        
        echo "?? System stopped. All networks, containers, and database volumes cleared."
        ;;
        
    *)
        echo "❌ Invalid mode: $MODE"
        echo "Usage: $0 [dev|prod|down|down-clean]"
        exit 1
        ;;
esac

echo "🎉 Done!"