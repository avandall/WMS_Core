-- Migration: Add UNIQUE constraint on products.name (TASK-079 / TECH-01)
-- Ensures SKU name uniqueness across database to prevent multiple results in .scalar() queries.

ALTER TABLE products ADD CONSTRAINT uq_products_name UNIQUE (name);
