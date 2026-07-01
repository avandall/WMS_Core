-- Phase 9 Migration: Add inventory_transactions table
-- This migration adds an immutable transaction ledger for inventory operations

CREATE TABLE inventory_transactions (
    id BIGSERIAL PRIMARY KEY,
    transaction_type VARCHAR(50) NOT NULL,
    document_id BIGINT,
    document_line_id BIGINT,
    product_id BIGINT NOT NULL,
    warehouse_id INTEGER NOT NULL,
    quantity INTEGER NOT NULL,
    physical_qty_before INTEGER,
    physical_qty_after INTEGER,
    reserved_qty_before INTEGER,
    reserved_qty_after INTEGER,
    available_qty_before INTEGER,
    available_qty_after INTEGER,
    user_id VARCHAR(100),
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    payload TEXT,
    idempotency_key VARCHAR(255) UNIQUE
);

-- Add indexes for filtering
CREATE INDEX ix_inventory_transactions_document_product ON inventory_transactions(document_id, product_id);
CREATE INDEX ix_inventory_transactions_warehouse_product ON inventory_transactions(warehouse_id, product_id);
CREATE INDEX ix_inventory_transactions_created_at ON inventory_transactions(created_at);
CREATE INDEX ix_inventory_transactions_document_id ON inventory_transactions(document_id);
CREATE INDEX ix_inventory_transactions_product_id ON inventory_transactions(product_id);
CREATE INDEX ix_inventory_transactions_warehouse_id ON inventory_transactions(warehouse_id);

-- Add unique constraint for idempotency
CREATE UNIQUE INDEX uq_inventory_transaction_idempotency ON inventory_transactions(idempotency_key) WHERE idempotency_key IS NOT NULL;
