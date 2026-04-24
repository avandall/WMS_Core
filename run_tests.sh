#!/bin/bash
set -e

# 1. Đảm bảo dùng đúng môi trường ảo
if [ -d ".venv" ]; then
    source .venv/bin/activate
fi

# 2. Thiết lập PYTHONPATH (Dùng đường dẫn tuyệt đối để chắc chắn)
export PYTHONPATH="$(pwd)/src:$(pwd)"

echo "--- Debug Info ---"
echo "Python Path: $(which python)"
echo "PYTHONPATH: $PYTHONPATH"
echo "------------------"

# 3. Chạy test thông qua module python để tránh lỗi import
python3 -m pytest "$@"