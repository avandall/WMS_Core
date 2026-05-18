## Phần 2: Về 2 file `_pb2.py` và `_pb2_grpc.py`

Câu hỏi của bạn cực kỳ chính xác: **Vâng, luôn luôn phải tạo ra 2 file này cho mọi trường hợp, mọi dự án dùng gRPC.**

*   **File `_pb2.py` (Protocol Buffers):** Chứa các Class dữ liệu (các message như `RobotLocation`, `RobotCommand`). Cứ mỗi khi bạn sửa hoặc thêm `message` trong file `.proto` $\rightarrow$ Bạn phải chạy lệnh dịch để cập nhật file này.
*   **File `_pb2_grpc.py` (gRPC):** Chứa các Class phục vụ cho việc truyền tải mạng (gồm `Stub` cho Client và `Servicer` cho Server).

### Làm sao bạn biết nó sinh ra hàm gì bên trong để mà gọi?

Đây chính là lúc bạn áp dụng **"Quy tắc dịch tên"** của gRPC. Bạn không cần mở 2 file đó ra đọc (vì máy viết rất rác và khó hiểu). Bạn chỉ cần nhìn vào file `.proto` do chính tay bạn thiết kế là biết ngay trong Python có hàm gì:

Hãy nhìn vào bảng quy đổi luật đặt tên này:

| Thứ bạn viết trong file `.proto` | Tên Class/Hàm tự động sinh ra trong Python | Cách bạn lôi ra dùng trong Code |
| :--- | :--- | :--- |
| `message RobotLocation` | Class `RobotLocation` | `robot_pb2.RobotLocation(...)` |
| `message RobotCommand` | Class `RobotCommand` | `robot_pb2.RobotCommand(...)` |
| `service RobotController` | Class Khung cho Server: **`[Tên Service]Servicer`** | `class ThucThi(robot_pb2_grpc.RobotControllerServicer):` |
| `service RobotController` | Class Điều khiển cho Client: **`[Tên Service]Stub`** | `stub = robot_pb2_grpc.RobotControllerStub(channel)` |
| `rpc ControlLoop (...)` | Hàm xử lý tên là **`ControlLoop`** | Server: `def ControlLoop(self, ...)` <br> Client: `stub.ControlLoop(...)` |

**Tóm lại quy luật:** 
*   Bạn định nghĩa Service tên là gì, thì cứ thêm đuôi `Servicer` (cho Server) hoặc `Stub` (cho Client) là ra tên Class trong Python.
*   Bạn định nghĩa `rpc` tên gì, thì trong Python biến thành một cái hàm viết y hệt tên đó.
*   Tất cả các Class dữ liệu nằm trong file `_pb2`. Tất cả các Class liên quan đến Service/Hàm/Kết nối nằm trong file `_pb2_grpc`.

---

## Bài học rút ra cho bạn

Sau này khi bạn tự làm một dự án Microservices mới:
1. Bạn tự tay viết file `.proto`. Bạn đặt tên service là `InventoryService`, hàm là `CheckStock`.
2. Bạn chạy lệnh biên dịch.
3. Trong code Python, bạn không cần mở file dịch ra xem. Bạn tự tin viết luôn:
   * Đầu Server: Kế thừa lớp `inventory_pb2_grpc.InventoryServiceServicer` và viết hàm `def CheckStock(self, request, context):`.
   * Đầu Client: Gọi `stub = inventory_pb2_grpc.InventoryServiceStub(channel)` và dùng `stub.CheckStock(...)`.

Bạn đã thấy quy luật của nó chưa? Bản chất của gRPC rất nhất quán, chỉ cần bạn nắm được luật dịch tên này là bạn tự làm chủ được nó mà không sợ đống hàm do máy sinh ra nữa!