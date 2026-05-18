import sys
from pathlib import Path
import grpc
from concurrent import futures
import os
import time

# Add project root to Python path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import grpc
from concurrent import futures
from lessons.gRPC.generate import robot_pb2
from lessons.gRPC.generate import robot_pb2_grpc

# Lớp xử lý Logic của Server
class LoggingInterceptor(grpc.ServerInterceptor):
    """Bộ gác cửa: Tự động ghi log mọi cuộc gọi từ Robot gửi lên Server"""

    def intercept_service(self, continuation, handler_call_details):
        # 1. Lấy tên hàm mà Client đang muốn gọi
        # Ví dụ: '/wms_robot.RobotController/ControlLoop'
        method_name = handler_call_details.method

        print(
            f"\n[BỐT GÁC] 🔔 Có một cuộc gọi đến hàm: {method_name} lúc {time.strftime('%X')}"
        )

        # 2. Cho phép cuộc gọi tiếp tục đi vào hàm xử lý chính
        return continuation(handler_call_details)


# ==========================================
# BƯỚC 2: LOGIC XỬ LÝ CHÍNH CỦA SERVER
# ==========================================
class RobotServicer(robot_pb2_grpc.RobotControllerServicer):

    def ControlLoop(self, request_iterator, context):
        # Hàm này bây giờ hoàn toàn sạch sẽ, chỉ tập trung vào logic nghiệp vụ WMS
        for location in request_iterator:
            print(
                f"   [LOGIC CHÍNH] Đang xử lý tọa độ của {location.robot_id}: X={location.xlocation}"
            )

            if location.xlocation > 100:
                yield robot_pb2.RobotCommand(action="STOP")
            else:
                yield robot_pb2.RobotCommand(action="KEEP_GOING")


# ==========================================
# BƯỚC 3: CẤU HÌNH INTERCEPTOR VÀO SERVER
# ==========================================
def serve():
    # Khởi tạo Interceptor của chúng ta
    logging_interceptor = LoggingInterceptor()

    # THAY ĐỔI Ở ĐÂY: Truyền interceptor vào hàm tạo grpc.server dưới dạng một danh sách (list)
    server = grpc.server(
        futures.ThreadPoolExecutor(max_workers=10),
        interceptors=(logging_interceptor,),
    )

    robot_pb2_grpc.add_RobotControllerServicer_to_server(
        RobotServicer(), server
    )
    server.add_insecure_port('[::]:50051')
    print("Server gRPC (có Bốt Gác) đang chạy tại port 50051...")
    server.start()
    server.wait_for_termination()

if __name__ == '__main__':
    serve()

    