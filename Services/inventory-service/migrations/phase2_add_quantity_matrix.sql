-- Phase 2 Migration: Add Quantity Matrix Fields
-- This migration adds physical_qty, reserved_qty, incoming_qty, in_transit_qty to warehouse_inventory
-- and backfills physical_qty from the existing quantity field

-- Add new columns with default values
ALTER TABLE warehouse_inventory 
ADD COLUMN physical_qty INTEGER NOT NULL DEFAULT 0,
ADD COLUMN reserved_qty INTEGER NOT NULL DEFAULT 0,
ADD COLUMN incoming_qty INTEGER NOT NULL DEFAULT 0,
ADD COLUMN in_transit_qty INTEGER NOT NULL DEFAULT 0;

-- Backfill physical_qty from existing quantity
UPDATE warehouse_inventory 
SET physical_qty = quantity;

-- Add check constraints for new fields
ALTER TABLE warehouse_inventory 
ADD CONSTRAINT check_warehouse_inventory_physical_qty_positive CHECK (physical_qty >= 0),
ADD CONSTRAINT check_warehouse_inventory_reserved_qty_positive CHECK (reserved_qty >= 0),
ADD CONSTRAINT check_warehouse_inventory_incoming_qty_positive CHECK (incoming_qty >= 0),
ADD CONSTRAINT check_warehouse_inventory_in_transit_qty_positive CHECK (in_transit_qty >= 0);

-- Add index for product/warehouse balance reads
CREATE INDEX ix_warehouse_inventory_product_warehouse ON warehouse_inventory (product_id, warehouse_id);

-- Verification: Ensure quantity == physical_qty for all rows
-- This should return 0 rows if migration was successful
SELECT COUNT(*) as mismatched_rows 
FROM warehouse_inventory 
WHERE quantity != physical_qty;
