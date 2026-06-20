# WMS Hybrid Microservices Architecture Plan

## 1. Overview

This plan addresses the complexity of maintaining data consistency across separate databases in a pure microservices architecture. Inspired by Odoo's approach, we propose a hybrid model where core WMS domain services share a database for ACID transactions and easy joins, while supporting services maintain separate databases for autonomy and scalability.

### 1.1 Problem Statement

The current microservices architecture with separate databases per service creates significant challenges:

- **Complex consistency management**: Cross-service transactions require distributed transaction patterns (Saga, 2PC)
- **Performance overhead**: Multiple service calls for simple joins between related entities
- **Data integrity risks**: Eventual consistency can lead to temporary inconsistencies in inventory operations
- **Development complexity**: Business logic that spans multiple services becomes harder to implement and test

### 1.2 Hybrid Solution

Share a database for tightly coupled core WMS services while maintaining separate databases for independent supporting services:

- **Shared Database (Core WMS Domain)**: Warehouse, Inventory, Product Catalog, Customer services
- **Separate Databases**: Identity, Documents, Audit, Reporting, AI services

## 2. Database Architecture

### 2.1 Shared Core Database (wms_core_db)

**Services sharing this database:**
- Warehouse Service
- Inventory Service  
- Product Catalog Service
- Customer Service

**Schema Organization:**
```
wms_core_db
├── schema_warehouse
│   ├── warehouses
│   ├── warehouse_locations
│   ├── warehouse_zones
│   ├── warehouse_operations
│   └── warehouse_configurations
├── schema_inventory
│   ├── inventory_items
│   ├── stock_levels
│   ├── inventory_transactions
│   ├── stock_reservations
│   └── inventory_adjustments
├── schema_products
│   ├── products
│   ├── product_variants
│   ├── product_categories
│   ├── product_units
│   └── product_metadata
└── schema_customers
    ├── customers
    ├── customer_addresses
    ├── customer_contacts
    └── customer_preferences
```

**Benefits:**
- ACID transactions across inventory movements, product updates, and warehouse operations
- Direct SQL joins for complex queries (e.g., inventory by warehouse location)
- Simplified business logic for stock allocation and fulfillment
- Single source of truth for core WMS data
- Easier data migration and rollback

### 2.2 Separate Databases

**Identity Database (identity_db):**
- users, positions, roles, permissions, tokens
- Independent for security isolation

**Documents Database (documents_db):**
- documents, document_metadata, file_references
- Independent for storage optimization

**Audit Database (audit_db):**
- audit_records, audit_logs
- Independent for compliance and retention policies

**Reporting Database (reporting_db):**
- materialized_views, aggregated_metrics, report_caches
- Can be read replicas or OLAP optimized

**AI Database (ai_db):**
- vector_store, embeddings, knowledge_index, ai_logs
- Specialized for vector operations and AI workloads

## 3. Service Architecture

### 3.1 Core WMS Services (Shared Database)

#### 3.1.1 Warehouse Service
- **Database**: wms_core_db (schema_warehouse)
- **Responsibilities**: 
  - Warehouse definitions, locations, zones
  - Warehouse capacity and configuration
  - Location management and optimization
- **Direct Access**: Full read/write to warehouse schema
- **Cross-Service Access**: Can join with inventory and product schemas

#### 3.1.2 Inventory Service
- **Database**: wms_core_db (schema_inventory)
- **Responsibilities**:
  - Stock levels, reservations, movements
  - Inventory transactions and allocations
  - Stock reconciliation and adjustments
- **Direct Access**: Full read/write to inventory schema
- **Cross-Service Access**: Can join with warehouse and product schemas

#### 3.1.3 Product Catalog Service
- **Database**: wms_core_db (schema_products)
- **Responsibilities**:
  - Product definitions, variants, categories
  - Product lifecycle and metadata
  - Unit of measure management
- **Direct Access**: Full read/write to product schema
- **Cross-Service Access**: Referenced by inventory service

#### 3.1.4 Customer Service
- **Database**: wms_core_db (schema_customers)
- **Responsibilities**:
  - Customer master data and relationships
  - Customer addresses and contacts
  - Customer-specific business rules
- **Direct Access**: Full read/write to customer schema
- **Cross-Service Access**: Referenced by order processing (future)

### 3.2 Supporting Services (Separate Databases)

#### 3.2.1 Identity Service
- **Database**: identity_db
- **Responsibilities**: Authentication, authorization, user management
- **Integration**: Provides JWT tokens, validates user context for core services

#### 3.2.2 Documents Service
- **Database**: documents_db
- **Responsibilities**: Document storage, metadata, search
- **Integration**: Stores document references, core services reference by ID

#### 3.2.3 Audit Service
- **Database**: audit_db
- **Responsibilities**: Audit logging, compliance tracking
- **Integration**: Receives events from core services via message broker

#### 3.2.4 Reporting Service
- **Database**: reporting_db
- **Integration**: Reads from core database via CDC or scheduled ETL

#### 3.2.5 AI Service
- **Database**: ai_db
- **Responsibilities**: AI queries, vector search, knowledge management
- **Integration**: Fetches data from core services via API, maintains own vector store

## 4. Data Access Patterns

### 4.1 Within Shared Database (Core Services)

**Direct Database Access:**
- Core services connect directly to wms_core_db
- Use schema-based isolation for service boundaries
- Database transactions span multiple schemas when needed
- Foreign keys can reference across schemas (with governance)

**Example Transaction:**
```sql
BEGIN;
-- Inventory service: Update stock level
UPDATE schema_inventory.stock_levels 
SET quantity = quantity - 10 
WHERE product_id = 123 AND warehouse_id = 456;

-- Warehouse service: Log operation
INSERT INTO schema_warehouse.warehouse_operations 
(warehouse_id, operation_type, quantity) 
VALUES (456, 'picking', 10);

-- Product service: Update product metrics (optional)
UPDATE schema_products.products 
SET total_picked = total_picked + 10 
WHERE id = 123;
COMMIT;
```

### 4.2 Cross-Database Communication

**API-Based Integration:**
- Core services call supporting services via REST/gRPC
- Supporting services never access core database directly
- All cross-boundary communication goes through APIs

**Event-Driven Integration:**
- Core services publish domain events to message broker
- Supporting services consume events for eventual consistency
- Audit service consumes all events for logging
- Reporting service consumes events for analytics

## 5. Transaction Management

### 5.1 Shared Database Transactions

**ACID Guarantees:**
- Full ACID support within wms_core_db
- Distributed transactions NOT needed for core WMS operations
- Simplified error handling and rollback

**Transaction Boundaries:**
- Service-level transactions for single-service operations
- Cross-service transactions for business processes (e.g., order fulfillment)
- Use database savepoints for nested operations

### 5.2 Cross-Database Transactions

**Saga Pattern:**
- For operations spanning core and supporting services
- Compensating transactions for rollback
- Event-driven orchestration

**Example: Document Upload with Inventory Update**
1. Documents Service: Upload document (documents_db)
2. Documents Service: Publish DocumentUploaded event
3. Inventory Service: Consume event, update inventory metadata (wms_core_db)
4. If step 3 fails: Publish DocumentUploadFailed event
5. Documents Service: Consume failure event, delete document (compensation)

## 6. Service Boundaries and Governance

### 6.1 Schema Governance

**Schema Ownership:**
- Each service owns its schema within shared database
- Service teams control schema changes for their domain
- Cross-schema changes require coordination

**Change Management:**
- Schema changes coordinated through DBA/architect review
- Migration scripts versioned and tested
- Backward compatibility maintained during transitions

### 6.2 API Boundaries

**Internal APIs:**
- Core services expose internal APIs for each other
- Versioned contracts for stability
- Can be optimized for performance (e.g., direct function calls in same deployment)

**External APIs:**
- All external access through API Gateway
- No direct database access from outside
- Consistent authentication and authorization

## 7. Migration Strategy

### 7.1 Current State Assessment

**Inventory:**
- Identify all existing databases per service
- Map data relationships and dependencies
- Catalog cross-service transactions and joins

### 7.2 Migration Phases

**Phase 1: Database Consolidation Planning**
1. Create shared database structure (wms_core_db)
2. Define schema boundaries and migration paths
3. Plan data migration scripts
4. Set up backup and rollback procedures

**Phase 2: Migrate Product Catalog Service**
1. Create schema_products in wms_core_db
2. Migrate data from product_service_db
3. Update Product Catalog Service to use shared database
4. Test all product-related functionality
5. Decommission old product_service_db

**Phase 3: Migrate Warehouse Service**
1. Create schema_warehouse in wms_core_db
2. Migrate data from warehouse_service_db
3. Update Warehouse Service to use shared database
4. Test all warehouse operations
5. Decommission old warehouse_service_db

**Phase 4: Migrate Inventory Service**
1. Create schema_inventory in wms_core_db
2. Migrate data from inventory_service_db
3. Update Inventory Service to use shared database
4. Implement cross-schema joins with warehouse and products
5. Test all inventory operations
6. Decommission old inventory_service_db

**Phase 5: Migrate Customer Service**
1. Create schema_customers in wms_core_db
2. Migrate data from customer_service_db
3. Update Customer Service to use shared database
4. Test all customer operations
5. Decommission old customer_service_db

**Phase 6: Optimize and Harden**
1. Implement cross-schema foreign keys (where appropriate)
2. Add database indexes for common join patterns
3. Optimize queries for shared database access
4. Update monitoring and alerting
5. Performance testing and tuning

### 7.3 Rollback Strategy

**Per-Phase Rollback:**
- Each phase can be rolled back independently
- Old databases kept in read-only mode until verification complete
- Application can switch back to old database via configuration

**Data Validation:**
- Compare data between old and new databases
- Verify record counts and relationships
- Test critical business operations
- Monitor for data consistency issues

## 8. Benefits and Trade-offs

### 8.1 Benefits

**Data Consistency:**
- ACID transactions for core WMS operations
- No distributed transaction complexity
- Immediate consistency for inventory operations

**Performance:**
- Direct joins for complex queries
- Reduced network overhead for cross-service operations
- Optimized for WMS-specific access patterns

**Development Simplicity:**
- Simplified business logic for core operations
- Easier debugging and testing
- Reduced cognitive load for developers

**Migration Path:**
- Incremental migration from current architecture
- Can revert individual services if needed
- Low-risk transition

### 8.2 Trade-offs

**Service Coupling:**
- Core services are coupled through shared database
- Schema changes require coordination
- Less independent deployment for core services

**Scaling Limits:**
- Shared database can become bottleneck
- Need to plan for database scaling (sharding, replication)
- Core services must scale together with database

**Operational Complexity:**
- Database becomes single point of failure for core services
- Need robust HA and backup strategies
- Database maintenance affects all core services

## 9. Deployment Architecture

### 9.1 Database Deployment

**High Availability:**
- Primary-replica setup for wms_core_db
- Automatic failover
- Regular backups and point-in-time recovery

**Scaling:**
- Read replicas for reporting and analytics
- Connection pooling for high concurrency
- Database sharding if needed (by warehouse or region)

### 9.2 Service Deployment

**Core Services:**
- Can be deployed independently (code changes)
- Must coordinate for database schema changes
- Share database connection pool configuration

**Supporting Services:**
- Fully independent deployment
- Separate databases and connection pools
- No coordination needed with core services

## 10. Monitoring and Observability

### 10.1 Database Monitoring

**Metrics:**
- Connection pool usage
- Query performance and slow queries
- Lock contention and deadlocks
- Transaction throughput and latency

**Alerting:**
- Database connection exhaustion
- Long-running transactions
- Replication lag
- Backup failures

### 10.2 Service Monitoring

**Core Services:**
- Database query performance per service
- Cross-service transaction rates
- Schema change impact
- API latency and error rates

**Supporting Services:**
- API call patterns to core services
- Event processing lag
- Database health for separate databases

## 11. Security Considerations

### 11.1 Database Access Control

**Schema-Level Security:**
- Each service has restricted access to its schema
- Cross-schema access controlled via database roles
- Audit all database access

**Connection Security:**
- Encrypted connections (TLS)
- Connection string security
- Credential rotation

### 11.2 Service-to-Service Security

**Authentication:**
- mTLS for internal service communication
- JWT tokens for API calls
- Service account management

**Authorization:**
- Service-level permissions
- API gateway enforcement
- Database role mapping

## 12. Testing Strategy

### 12.1 Database Testing

**Unit Tests:**
- Test each service's database operations
- Mock cross-service dependencies
- Test transaction rollback scenarios

**Integration Tests:**
- Test cross-schema operations
- Test concurrent access patterns
- Test database migration scripts

### 12.2 Service Testing

**Contract Tests:**
- Test API contracts between services
- Verify event schemas
- Test backward compatibility

**End-to-End Tests:**
- Test complete business processes
- Test failure scenarios
- Test rollback procedures

## 13. Implementation Roadmap

### 13.1 Preparation (Week 1-2)
- [ ] Create detailed data migration scripts
- [ ] Set up wms_core_db infrastructure
- [ ] Define schema governance process
- [ ] Create rollback procedures

### 13.2 Phase 1: Product Catalog (Week 3-4)
- [ ] Migrate Product Catalog Service to shared database
- [ ] Test and validate
- [ ] Cut over traffic
- [ ] Monitor and optimize

### 13.3 Phase 2: Warehouse Service (Week 5-6)
- [ ] Migrate Warehouse Service to shared database
- [ ] Implement cross-schema joins with products
- [ ] Test and validate
- [ ] Cut over traffic

### 13.4 Phase 3: Inventory Service (Week 7-8)
- [ ] Migrate Inventory Service to shared database
- [ ] Implement complex inventory transactions
- [ ] Test and validate
- [ ] Cut over traffic

### 13.5 Phase 4: Customer Service (Week 9-10)
- [ ] Migrate Customer Service to shared database
- [ ] Test and validate
- [ ] Cut over traffic

### 13.6 Optimization (Week 11-12)
- [ ] Implement cross-schema foreign keys
- [ ] Optimize queries and indexes
- [ ] Performance testing
- [ ] Documentation updates

## 14. Success Criteria

**Functional:**
- All core WMS operations work correctly
- Data consistency maintained across all operations
- No data loss during migration
- Rollback capability verified

**Performance:**
- Query performance improved or maintained
- Reduced latency for cross-service operations
- Database handles peak load without degradation

**Operational:**
- Clear monitoring and alerting in place
- Documented runbooks for common issues
- Team trained on new architecture
- Governance process established

## 15. Conclusion

This hybrid architecture provides the best of both worlds:

- **Monolith benefits**: ACID transactions, easy joins, data consistency for core WMS operations
- **Microservices benefits**: Independent deployment for supporting services, technology flexibility, scalability

The shared database approach for core WMS services addresses the complexity of maintaining consistency across separate databases while preserving the microservices architecture for services that benefit from independence.

This plan provides a clear migration path from the current architecture to a more maintainable and performant system, with minimal risk and clear rollback options at each phase.
