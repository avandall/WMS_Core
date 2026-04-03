-- ========================================
-- WMS Master Data Seed Script
-- ========================================

-- Insert Warehouses
INSERT INTO warehouses (location) VALUES 
('123 Lê Lợi, Quận 1, HCM'),
('456 Võ Văn Ngân, Thủ Đức, HCM'),
('789 Tân Kỷ Tân, Bình Tân, HCM'),
('321 Quốc Lộ 1A, Hóc Môn, HCM'),
('656 Huỳnh Tấn Phát, Bình Chánh, HCM');

-- Insert Products
INSERT INTO products (name, price, description) VALUES 
('Pallet Gỗ tiêu chuẩn', 150000, 'Pallet gỗ thông dụng 1200x1000mm'),
('Xe nâng điện', 45000000, 'Xe nâng điện 1.5 tấn, loại mới'),
('Thùng carton 3 lớp', 8500, 'Thùng carton 50x40x30cm'),
('Màng bọc PE', 12000, 'Màng bọc PE dày 0.03mm, cuộn 1kg'),
('Kệ sắt V lỗ', 750000, 'Kệ sắt V lỗ 1500x500x2000mm'),
('Xe đẩy hàng', 2800000, 'Xe đẩy hàng inox 200kg'),
('Bao tải PP', 3500, 'Bao tải PP 50kg màu trắng'),
('Dây đeo hàng', 15000, 'Dây đeo hàng polyester 5m'),
('Thùng nhựa', 45000, 'Thùng nhựa 60L có nắp'),
('Kẹp chì', 2500, 'Kẹp chì nhôm 10mm'),
('Máy in mã vạch', 8500000, 'Máy in mã vạch Zebra ZD220'),
('Băng keo', 18000, 'Băng keo trong 100y'),
('Giấy in hóa đơn', 12000, 'Giấy in hóa đơn 2 liên'),
('Bút laser', 95000, 'Bút laser đo khoảng cách 50m'),
('Đồng hồ treo tường', 150000, 'Đồng hồ treo tường 30cm'),
('Bàn làm việc', 3200000, 'Bàn làm việc sắt 120x60cm'),
('Ghế văn phòng', 1850000, 'Ghế văn phòng lưới lưng cao'),
('Laptop Dell', 18500000, 'Laptop Dell Core i5 8GB RAM'),
('Máy tính để bàn', 12500000, 'Máy tính để bàn Core i3 8GB RAM'),
('Màn hình LCD', 4500000, 'Màn hình LCD 24 inch Full HD'),
('Bàn phím cơ', 950000, 'Bàn phím cơ RGB'),
('Chuột không dây', 450000, 'Chuột không dây Logitech');

-- Insert Users (for audit and document tracking)
INSERT INTO users (email, hashed_password, role, full_name, is_active, created_at) VALUES 
('admin@wms.vn', '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewdBPj6ukx.LFvO6', 'admin', 'Administrator', 1, NOW()),
('manager@wms.vn', '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewdBPj6ukx.LFvO6', 'manager', 'Warehouse Manager', 1, NOW()),
('staff@wms.vn', '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewdBPj6ukx.LFvO6', 'staff', 'Warehouse Staff', 1, NOW()),
('supervisor@wms.vn', '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewdBPj6ukx.LFvO6', 'supervisor', 'Supervisor', 1, NOW());

-- Insert Customers
INSERT INTO customers (name, email, phone, address, debt_balance, created_at) VALUES 
('Công ty ABC', 'contact@abc.com', '0901234567', '123 Nguyễn Trãi, Q1, HCM', 0.0, NOW()),
('Công ty XYZ', 'info@xyz.vn', '0912345678', '456 Trần Hưng Đạo, Q5, HCM', 0.0, NOW()),
('Siêu thị Co.opmart', 'donhang@coopmart.vn', '0923456789', '789 Cộng Hòa, Tân Bình, HCM', 0.0, NOW()),
('Chuỗi cửa hàng Tiki', 'business@tiki.vn', '0934567890', '321 Võ Văn Kiệt, Q1, HCM', 0.0, NOW()),
('Cửa hàng tiện lợi 24/7', 'order@247store.vn', '0945678901', '656 Phạm Văn Đồng, Phú Nhuận, HCM', 0.0, NOW());

-- Insert initial inventory (some products in some warehouses)
INSERT INTO warehouse_inventory (warehouse_id, product_id, quantity) VALUES 
(1, 1, 100),  -- Pallet Gỗ in Kho Q1
(2, 1, 5),    -- Xe nâng in Kho Q1
(3, 1, 500),  -- Thùng carton in Kho Q1
(4, 1, 200),  -- Màng bọc in Kho Q1
(5, 2, 50),   -- Kệ sắt in Kho Thủ Đức
(6, 2, 20),   -- Xe đẩy in Kho Thủ Đức
(7, 3, 1000), -- Bao tải in Kho Bình Tân
(8, 4, 300),  -- Dây đeo in Kho Hóc Môn
(9, 5, 150),  -- Thùng nhựa in Kho Bình Chánh
(10, 1, 100), -- Kẹp chì in Kho Q1
(11, 2, 3),   -- Máy in mã vạch in Kho Thủ Đức
(12, 3, 800), -- Băng keo in Kho Bình Tân
(13, 4, 200), -- Giấy in hóa đơn in Kho Hóc Môn
(14, 5, 50),  -- Bút laser in Kho Bình Chánh
(15, 1, 25),  -- Đồng hồ in Kho Q1
(16, 2, 15),  -- Bàn làm việc in Kho Thủ Đức
(17, 3, 30),  -- Ghế văn phòng in Kho Bình Tân
(18, 4, 10),  -- Laptop in Kho Hóc Môn
(19, 5, 20),  -- Máy tính để bàn in Kho Bình Chánh
(20, 1, 35),  -- Màn hình in Kho Q1
(21, 2, 60),  -- Bàn phím cơ in Kho Thủ Đức
(22, 3, 100); -- Chuột không dây in Kho Bình Tân

-- Insert sample documents for testing
INSERT INTO documents (doc_type, from_warehouse_id, to_warehouse_id, created_by, status, total_value) VALUES 
('IMPORT', NULL, 1, 'admin@wms.vn', 'POSTED', 50000000),  -- Nhập hàng cho Kho Q1
('IMPORT', NULL, 2, 'manager@wms.vn', 'POSTED', 25000000), -- Nhập hàng cho Kho Thủ Đức
('EXPORT', 1, NULL, 'staff@wms.vn', 'POSTED', 15000000),   -- Xuất hàng từ Kho Q1
('TRANSFER', 1, 2, 'supervisor@wms.vn', 'POSTED', 10000000), -- Chuyển hàng Q1 -> Thủ Đức
('SALE', 2, NULL, 'manager@wms.vn', 'POSTED', 8000000);   -- Bán hàng từ Kho Thủ Đức

-- Insert document items
INSERT INTO document_items (document_id, product_id, quantity, unit_price) VALUES 
-- Items for IMPORT document 1
(1, 1, 50, 150000),   -- 50 Pallet Gỗ
(1, 3, 200, 8500),    -- 200 Thùng carton
(1, 4, 100, 12000),   -- 100 Màng bọc
-- Items for IMPORT document 2  
(2, 5, 20, 750000),   -- 20 Kệ sắt
(2, 6, 10, 2800000),  -- 10 Xe đẩy
-- Items for EXPORT document 3
(3, 7, 100, 3500),    -- 100 Bao tải
(3, 8, 50, 15000),    -- 50 Dây đeo
-- Items for TRANSFER document 4
(4, 9, 25, 45000),    -- 25 Thùng nhựa
(4, 10, 50, 2500),    -- 50 Kẹp chì
-- Items for SALE document 5
(5, 11, 2, 8500000),  -- 2 Máy in mã vạch
(5, 12, 200, 18000);  -- 200 Băng keo

-- Insert positions for warehouses
INSERT INTO positions (warehouse_id, position_code, location_description) VALUES 
-- Kho Q1 positions
(1, 'A-01-01', 'Khu A, Dãy 01, Vị trí 01'),
(1, 'A-01-02', 'Khu A, Dãy 01, Vị trí 02'),
(1, 'A-02-01', 'Khu A, Dãy 02, Vị trí 01'),
(1, 'B-01-01', 'Khu B, Dãy 01, Vị trí 01'),
(1, 'B-01-02', 'Khu B, Dãy 01, Vị trí 02'),
-- Kho Thủ Đức positions
(2, 'C-01-01', 'Khu C, Dãy 01, Vị trí 01'),
(2, 'C-01-02', 'Khu C, Dãy 01, Vị trí 02'),
(2, 'D-01-01', 'Khu D, Dãy 01, Vị trí 01'),
(2, 'D-02-01', 'Khu D, Dãy 02, Vị trí 01'),
-- Kho Bình Tân positions
(3, 'E-01-01', 'Khu E, Dãy 01, Vị trí 01'),
(3, 'E-01-02', 'Khu E, Dãy 01, Vị trí 02'),
(3, 'F-01-01', 'Khu F, Dãy 01, Vị trí 01'),
-- Kho Hóc Môn positions
(4, 'G-01-01', 'Khu G, Dãy 01, Vị trí 01'),
(4, 'G-02-01', 'Khu G, Dãy 02, Vị trí 01'),
-- Kho Bình Chánh positions
(5, 'H-01-01', 'Khu H, Dãy 01, Vị trí 01'),
(5, 'H-01-02', 'Khu H, Dãy 01, Vị trí 02');

-- Insert position inventory (products at specific positions)
INSERT INTO position_inventory (position_id, product_id, quantity) VALUES 
(1, 1, 25),   -- Pallet Gỗ at A-01-01
(1, 3, 100),  -- Thùng carton at A-01-01
(2, 1, 25),   -- Pallet Gỗ at A-01-02
(2, 4, 100),  -- Màng bọc at A-01-02
(3, 2, 3),    -- Xe nâng at A-02-01
(3, 10, 50),  -- Kẹp chì at A-02-01
(6, 5, 25),   -- Kệ sắt at C-01-02
(6, 6, 5),    -- Xe đẩy at C-01-02
(7, 5, 25),   -- Kệ sắt at C-01-02
(7, 11, 2),   -- Máy in mã vạch at C-01-02
(11, 7, 500), -- Bao tải at E-01-01
(11, 12, 400),-- Băng keo at E-01-01
(12, 7, 500), -- Bao tải at E-01-02
(12, 12, 400),-- Băng keo at E-01-02
(13, 8, 150), -- Dây đeo at F-01-01
(13, 13, 100),-- Giấy in hóa đơn at F-01-01
(14, 9, 75),  -- Thùng nhựa at G-01-01
(14, 14, 25), -- Bút laser at G-01-01
(15, 9, 75),  -- Thùng nhựa at G-02-01
(15, 15, 25), -- Đồng hồ at G-02-01
(16, 10, 50), -- Kẹp chì at H-01-01
(16, 21, 30), -- Bàn phím cơ at H-01-01
(17, 22, 50); -- Chuột không dây at H-01-02

-- Insert audit events for document tracking
INSERT INTO audit_events (entity_type, entity_id, action, user_id, warehouse_id, old_values, new_values, created_at) VALUES 
('document', 1, 'CREATED', 1, 1, NULL, '{"doc_type": "IMPORT", "status": "DRAFT"}', NOW()),
('document', 1, 'POSTED', 1, 1, '{"status": "DRAFT"}', '{"status": "POSTED"}', NOW()),
('document', 2, 'CREATED', 2, 2, NULL, '{"doc_type": "IMPORT", "status": "DRAFT"}', NOW()),
('document', 2, 'POSTED', 2, 2, '{"status": "DRAFT"}', '{"status": "POSTED"}', NOW()),
('document', 3, 'CREATED', 3, 1, NULL, '{"doc_type": "EXPORT", "status": "DRAFT"}', NOW()),
('document', 3, 'POSTED', 3, 1, '{"status": "DRAFT"}', '{"status": "POSTED"}', NOW()),
('document', 4, 'CREATED', 4, 1, NULL, '{"doc_type": "TRANSFER", "status": "DRAFT"}', NOW()),
('document', 4, 'POSTED', 4, 1, '{"status": "DRAFT"}', '{"status": "POSTED"}', NOW()),
('document', 5, 'CREATED', 2, 2, NULL, '{"doc_type": "SALE", "status": "DRAFT"}', NOW()),
('document', 5, 'POSTED', 2, 2, '{"status": "DRAFT"}', '{"status": "POSTED"}', NOW());