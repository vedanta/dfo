# Database Migrations

This file tracks schema changes and migration instructions for the DuckDB database.

## Overview

Since we're using DuckDB for local storage in the MVP phase, migrations are handled manually using the `dfo db refresh` command. For production use, consider implementing automated migrations (e.g., Alembic, yoyo-migrations).

---

## Migration History

### Migration 002 - Add subscription_id to vm_inventory (2025-01-20)

**Commit:** `33717f1`

**Change:**
Added `subscription_id` column to `vm_inventory` table to track which Azure subscription each VM belongs to.

**Schema Change:**
```sql
-- Before
CREATE TABLE vm_inventory (
    vm_id TEXT,
    name TEXT,
    ...
);

-- After
CREATE TABLE vm_inventory (
    vm_id TEXT,
    subscription_id TEXT,  -- NEW
    name TEXT,
    ...
);
```

**Migration Required:** Yes

**How to Apply:**
```bash
./dfo.sh db refresh --yes
```

**Breaking Change:** Yes - existing databases will need to be refreshed (data will be cleared)

**Impact:**
- All existing VM inventory data will be lost
- Re-discovery required after migration
- VMInventory model now requires subscription_id parameter

---

### Migration 001 - Initial Schema (2025-01-15)

**Commit:** `14b5a38`

**Change:**
Initial database schema creation for MVP.

**Tables Created:**
- `vm_inventory` - VM metadata and CPU timeseries
- `vm_idle_analysis` - Idle VM analysis results
- `vm_actions` - Action execution log

**Migration Required:** No (initial setup)

**How to Apply:**
```bash
./dfo.sh db init
```

---

## Future Migration Strategy

For production deployments beyond MVP, consider:

1. **Automated Migrations:** Use a migration tool (Alembic, yoyo-migrations)
2. **Versioning:** Track schema version in database
3. **Rollback Support:** Provide down migrations
4. **Data Preservation:** Implement proper ALTER TABLE migrations instead of drop/recreate
5. **Backup Strategy:** Automated backups before migrations

**Example production migration workflow:**
```bash
# Backup database
cp dfo.duckdb dfo.duckdb.backup

# Run migration
dfo db migrate --target 002

# Verify
dfo db info
```

---

## Checking Your Schema Version

To see your current schema structure:

```bash
# View all tables
./dfo.sh db info

# View specific table schema
python3 << 'EOF'
import duckdb
conn = duckdb.connect('./dfo.duckdb')
result = conn.execute("DESCRIBE vm_inventory").fetchall()
for row in result:
    print(f"{row[0]:<20} {row[1]}")
conn.close()
EOF
```

---

## Notes

- **MVP Approach:** Simple drop/recreate for schema changes
- **Data Loss:** `db refresh` clears all data - re-run discovery after migration
- **Production:** Implement proper migration tooling before production use
- **Backwards Compatibility:** Breaking changes documented above
