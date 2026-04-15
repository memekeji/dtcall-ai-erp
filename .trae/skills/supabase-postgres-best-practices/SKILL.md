---
name: "supabase-postgres-best-practices"
description: "Postgres performance optimization guide with query, schema, security, and indexing best practices. Invoke when writing SQL queries, designing database schemas, or optimizing database performance."
---

# Supabase Postgres Best Practices

Comprehensive performance optimization guide for Postgres, maintained by Supabase. Contains rules across 8 categories, prioritized by impact to guide automated query optimization and schema design.

## When to Apply

Reference these guidelines when:

- Writing SQL queries or designing schemas
- Implementing indexes or query optimization
- Reviewing database performance issues
- Configuring connection pooling or scaling
- Optimizing for Postgres-specific features
- Working with Row-Level Security (RLS)

## Rule Categories by Priority

| Priority | Category | Impact | Prefix |
|----------|----------|--------|--------|
| 1 | Query Performance | CRITICAL | `query-` |
| 2 | Connection Management | CRITICAL | `conn-` |
| 3 | Security & RLS | CRITICAL | `security-` |
| 4 | Schema Design | HIGH | `schema-` |
| 5 | Concurrency & Locking | MEDIUM-HIGH | `lock-` |
| 6 | Data Access Patterns | MEDIUM | `data-` |
| 7 | Monitoring & Diagnostics | LOW-MEDIUM | `monitor-` |
| 8 | Advanced Features | LOW | `advanced-` |

## How to Use

Read individual rule files for detailed explanations and SQL examples:

- `references/query-missing-indexes.md`
- `references/schema-partial-indexes.md`
- `references/_sections.md`

Each rule file contains:

- Brief explanation of why it matters
- Incorrect SQL example with explanation
- Correct SQL example with explanation
- Optional EXPLAIN output or metrics
- Additional context and references
- Supabase-specific notes (when applicable)

## References

- [PostgreSQL Documentation](https://www.postgresql.org/docs/current/)
- [Supabase Docs](https://supabase.com/docs)
- [PostgreSQL Wiki - Performance Optimization](https://wiki.postgresql.org/wiki/Performance_Optimization)
- [Supabase Database Overview](https://supabase.com/docs/guides/database/overview)
- [Supabase Row-Level Security](https://supabase.com/docs/guides/auth/row-level-security)

## Key Rules

### Query Performance (CRITICAL)

- Always use EXPLAIN to analyze query plans
- Avoid SELECT * - specify columns explicitly
- Use WHERE clauses to filter early
- Use JOINs instead of subqueries when appropriate
- Implement proper indexing strategy

### Connection Management (CRITICAL)

- Use connection pooling (Supabase uses PgBouncer)
- Don't create new connections per request
- Configure pool sizes appropriately
- Handle connection exhaustion

### Security & RLS (CRITICAL)

- Always enable RLS on tables
- Write secure RLS policies
- Test RLS policies thoroughly
- Use service role only when necessary

### Schema Design (HIGH)

- Use appropriate data types
- Normalize where it makes sense
- Denormalize for read performance when needed
- Use constraints (NOT NULL, CHECK, etc.)

### Concurrency & Locking

- Understand row-level vs table-level locks
- Use advisory locks for application-level coordination
- Avoid long-running transactions
- Handle deadlocks appropriately
