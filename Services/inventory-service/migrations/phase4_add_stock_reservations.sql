-- Phase 4 Migration: Add stock_reservations table
-- This migration adds the stock_reservations table to support persistent reservations

CREATE TABLE stock_reservations (
    id BIGSERIAL PRIMARY KEY,
    source_type VARCHAR(50) NOT NULL,
    source_id BIGINT,
    document_id BIGINT,
    product_id BIGINT NOT NULL,
    warehouse_id INTEGER NOT NULL,
    requested_qty INTEGER NOT NULL,
    reserved_qty INTEGER NOT NULL DEFAULT 0,
    released_qty INTEGER NOT NULL DEFAULT 0,
    consumed_qty INTEGER NOT NULL DEFAULT 0,
    status VARCHAR(50) NOT NULL DEFAULT 'PENDING',
    expires_at TIMESTAMP,
    created_by VARCHAR(255),
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    idempotency_key VARCHAR(255) UNIQUE
);

-- Add indexes for performance
CREATE INDEX ix_stock_reservations_product_warehouse ON stock_reservations (product_id, warehouse_id);
CREATE INDEX ix_stock_reservations_document_id ON stock_reservations (document_id);
CREATE INDEX ix_stock_reservations_status ON stock_reservations (status);
CREATE INDEX ix_stock_reservations_expires_at ON stock_reservations (expires_at);

-- Add unique constraints for idempotency and source tracking
CREATE UNIQUE CONSTRAINT uq_stock_reservation_idempotency ON stock_reservations (idempotency_key) WHERE idempotency_key IS NOT NULL;
CREATE UNIQUE CONSTRAINT uq_stock_reservation_source ON stock_reservations (source_type, source_id) WHERE source_id IS NOT NULL;

-- Add trigger to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_stock_reservations_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_stock_reservations_updated_at
    BEFORE UPDATE ON stock_reservations
    FOR EACH ROW
    EXECUTE FUNCTION update_stock_reservations_updated_at();
