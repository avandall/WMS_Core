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
        echo "🔧 If no data appears, run: ./fix_seed_data.sh"
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
        echo "🛑 Stopping WMS and cleaning up all resources..."
        # --profile "*" : Tắt sạch mọi service thuộc bất kỳ profile nào (adminer, v.v.)
        # --remove-orphans : Xóa các container cũ không còn nằm trong file config
        # -v : Xóa các volume dữ liệu (nếu bạn muốn giữ dữ liệu DB thì bỏ flag -v này)
        docker compose --env-file .env.docker --profile "*" down -v --remove-orphans
        
        echo "✅ System stopped. All networks and containers cleared."
        ;;
        
    *)
        echo "❌ Invalid mode: $MODE"
        echo "Usage: $0 [dev|prod|down]"
        exit 1
        ;;
esac

echo "🎉 Done!"