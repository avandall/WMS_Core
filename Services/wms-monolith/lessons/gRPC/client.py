import grpc
import time
import random
import sys
import os
from pathlib import Path

# Add project root to Python path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from lessons.gRPC.generate import robot_pb2
from lessons.gRPC.generate import robot_pb2_grpc

# 1. Hàm tạo ra dòng chảy tọa độ (Generator)
def generate_locations():
    robot_id = "Robot_001"
    x = 0
    while True:
        x += random.randint(10, 30) # Robot tiến về phía trước
        y = random.randint(0, 50)
        
        print(f"Robot đang ở: X={x}, Y={y}")
        
        # 'yield' gửi từng tọa độ một qua ống dẫn
        yield robot_pb2.RobotLocation(robot_id=robot_id, xlocation=x, ylocation=y)
        
        time.sleep(1) # Chờ 1 giây rồi gửi tiếp
        if x > 200: # Giả lập Robot dừng lại sau khi đi xa
            break

def run():
    # 2. Kết nối tới Server (insecure vì ta dùng add_insecure_port ở server)
    with grpc.insecure_channel('localhost:50051') as channel:
        stub = robot_pb2_grpc.RobotControllerStub(channel)
        
        print("--- Đang bắt đầu gửi Stream tọa độ (Bi-directional) ---")
        
        # 3. Gọi hàm ControlLoop (Gửi Stream và Nhận Stream)
        # 'responses' cũng là một iterator chứa các lệnh từ Server gửi xuống
        responses = stub.ControlLoop(generate_locations())
        
        try:
            for cmd in responses:
                print(f"SẾP RA LỆNH: {cmd.action}")
                if cmd.action == "STOP":
                    print("Robot đã dừng lại theo lệnh!")
                    break
        except grpc.RpcError as e:
            print(f"Lỗi kết nối: {e}")

if __name__ == '__main__':
    run()