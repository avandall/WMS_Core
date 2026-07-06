-- Phase 6 Migration: Add document lifecycle fields
-- This migration adds header and line fields to prepare documents for operational request lifecycle

-- Add document header lifecycle fields
ALTER TABLE documents 
ADD COLUMN transaction_type VARCHAR(50),
ADD COLUMN reason_code VARCHAR(50),
ADD COLUMN requested_by VARCHAR(100),
ADD COLUMN approved_at TIMESTAMP,
ADD COLUMN execution_started_at TIMESTAMP,
ADD COLUMN completed_at TIMESTAMP,
ADD COLUMN assigned_to VARCHAR(100);

-- Add document line lifecycle fields
ALTER TABLE document_items 
ADD COLUMN requested_qty INTEGER,
ADD COLUMN reserved_qty INTEGER DEFAULT 0,
ADD COLUMN executed_qty INTEGER,
ADD COLUMN rejected_qty INTEGER DEFAULT 0,
ADD COLUMN difference_qty INTEGER DEFAULT 0,
ADD COLUMN execution_status VARCHAR(50);

-- Backfill requested_qty from existing quantity for existing document items
UPDATE document_items SET requested_qty = quantity WHERE requested_qty IS NULL;

-- Add indexes for new lifecycle fields
CREATE INDEX ix_documents_transaction_type ON documents(transaction_type);
CREATE INDEX ix_documents_approved_at ON documents(approved_at);
CREATE INDEX ix_documents_execution_started_at ON documents(execution_started_at);
CREATE INDEX ix_documents_completed_at ON documents(completed_at);
CREATE INDEX ix_document_items_execution_status ON document_items(execution_status);
