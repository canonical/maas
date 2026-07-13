# Repository Contracts: Custom Boot Assets

**Feature Branch**: `6688-custom-boot-assets`  
**Date**: 2025-07-18  
**Updated**: 2025-07-18 — Simplified endpoint strategy (removed get_versions, list-specific queries)

---

## Extended Repository: `BootResourcesRepository`

**Location**: `src/maasservicelayer/db/repositories/bootresources.py`  
**Base Class**: `BaseRepository[BootResource]` (existing)  
**Table**: `BootResourceTable`

**Rationale**: The existing `BootResourcesRepository` already provides base CRUD operations on the same table. Adding custom boot asset query methods and extending `BootResourceClauseFactory` with new clause filters follows the established pattern. The existing CRUD methods (`find`, `get_by_id`, `delete`, `delete_many`) handle all list/get/delete operations called by `CustomImagesHandler`.

---

### Extended ClauseFactory: `BootResourceClauseFactory`

**Existing location**: `src/maasservicelayer/db/repositories/bootresources.py`

New clause methods added to the existing `BootResourceClauseFactory`:

```python
class BootResourceClauseFactory:
    # ... existing clauses ...

    @classmethod
    def with_uploaded_type(cls) -> Clause:
        """Filter to only custom uploaded assets (rtype=UPLOADED)."""
        return Clause(condition=eq(BootResourceTable.c.rtype, BootResourceType.UPLOADED))

    @classmethod
    def with_asset_type_bootloader(cls) -> Clause:
        """Filter to bootloader assets only (bootloader_type IS NOT NULL)."""
        return Clause(condition=BootResourceTable.c.bootloader_type.isnot(None))

    @classmethod
    def with_asset_type_kernel(cls) -> Clause:
        """Filter to kernel assets only (bootloader_type IS NULL, kflavor IS NOT NULL)."""
        return Clause(condition=and_(
            BootResourceTable.c.bootloader_type.is_(None),
            BootResourceTable.c.kflavor.isnot(None),
        ))

    @classmethod
    def with_asset_type_image(cls) -> Clause:
        """Filter to plain image assets (bootloader_type IS NULL, kflavor IS NULL)."""
        return Clause(condition=and_(
            BootResourceTable.c.bootloader_type.is_(None),
            BootResourceTable.c.kflavor.is_(None),
        ))

    @classmethod
    def with_kflavor(cls, kflavor: str) -> Clause:
        """Filter by kernel flavour."""
        return Clause(condition=eq(BootResourceTable.c.kflavor, kflavor))

    @classmethod
    def with_bootloader_identity(cls, name: str, architecture: str) -> Clause:
        """Match bootloader identity: name + architecture + rtype=UPLOADED."""
        return Clause(condition=and_(
            eq(BootResourceTable.c.rtype, BootResourceType.UPLOADED),
            eq(BootResourceTable.c.name, name),
            eq(BootResourceTable.c.architecture, architecture),
            BootResourceTable.c.bootloader_type.isnot(None),
        ))

    @classmethod
    def with_kernel_identity(cls, name: str, architecture: str, kflavor: str) -> Clause:
        """Match kernel identity: name + architecture + kflavor + rtype=UPLOADED."""
        return Clause(condition=and_(
            eq(BootResourceTable.c.rtype, BootResourceType.UPLOADED),
            eq(BootResourceTable.c.name, name),
            eq(BootResourceTable.c.architecture, architecture),
            eq(BootResourceTable.c.kflavor, kflavor),
            BootResourceTable.c.bootloader_type.is_(None),
        ))
```

**Usage by existing list endpoint**: The `type` filter parameter on `list_custom_images` will build a `QuerySpec` using `with_asset_type_bootloader()`, `with_asset_type_kernel()`, or `with_asset_type_image()` in addition to the existing `with_uploaded_type()` clause.

---

### Method: `find_or_create_bootloader`

```python
async def find_or_create_bootloader(
    self,
    name: str,
    architecture: str,
) -> tuple[BootResource, bool]:
    """
    Find existing bootloader resource or create new one.
    Returns (resource, created) tuple.
    """
```

**Query** (find):
```sql
SELECT * FROM maas_bootresource
WHERE rtype = 2
  AND name = :name
  AND architecture = :architecture
  AND bootloader_type IS NOT NULL
LIMIT 1;
```

If not found (create):
```sql
INSERT INTO maas_bootresource (rtype, name, architecture, bootloader_type, kflavor, rolling)
VALUES (2, :name, :architecture, 'custom', NULL, false)
RETURNING *;
```

---

### Method: `find_or_create_kernel`

```python
async def find_or_create_kernel(
    self,
    name: str,
    architecture: str,
    kflavor: str,
) -> tuple[BootResource, bool]:
    """
    Find existing kernel resource or create new one.
    Returns (resource, created) tuple.
    """
```

**Query** (find):
```sql
SELECT * FROM maas_bootresource
WHERE rtype = 2
  AND name = :name
  AND architecture = :architecture
  AND kflavor = :kflavor
  AND bootloader_type IS NULL
LIMIT 1;
```

---

### Method: `get_latest_version`

```python
async def get_latest_version(
    self,
    resource_id: int,
) -> BootResourceSet | None:
    """Get the latest version (BootResourceSet) for a resource."""
```

**Query**:
```sql
SELECT * FROM maas_bootresourceset
WHERE resource_id = :resource_id
ORDER BY id DESC
LIMIT 1;
```

**Note**: Order by `id DESC` rather than lexicographic version because IDs are monotonically increasing and handle the `YYYYMMDD.N` format edge cases correctly.

---

### Method: `get_bootloader_for_architecture`

```python
async def get_bootloader_for_architecture(
    self,
    bootloader_name: str,
    architecture: str,
) -> BootResource | None:
    """
    Find a custom bootloader resource by name and architecture.
    Used by DHCP host declaration generation to resolve the bootloader
    path for machines deployed with a custom bootloader.
    """
```

**Query**:
```sql
SELECT br.*
FROM maas_bootresource br
WHERE br.rtype = 2
  AND br.name = :bootloader_name
  AND br.architecture = :architecture
  AND br.bootloader_type IS NOT NULL
LIMIT 1;
```

---

### Method: `get_bootloader_file_for_set`

```python
async def get_bootloader_file_for_set(
    self,
    resource_set_id: int,
) -> BootResourceFile | None:
    """
    Get the primary bootloader file for a boot resource set.
    Used by DHCP config generation to compute the boot filename path.
    """
```

**Query**:
```sql
SELECT brf.*
FROM maas_bootresourcefile brf
JOIN maas_bootresourceset brs ON brf.resource_set_id = brs.id
JOIN maas_bootresource br ON brs.resource_id = br.id
WHERE brs.id = :resource_set_id
  AND br.bootloader_type IS NOT NULL
  AND brf.filetype = 'bootloader'
LIMIT 1;
```

---

## Existing Repositories (Reused Without Changes)

### `BootResourcesRepository`

**Existing methods reused by `CustomImagesHandler`** (no modifications):
- `find(spec: QuerySpec)` — used by list endpoint (add type clause to spec)
- `get_by_id(id)` — used by get-by-ID endpoint
- `delete(id)` — used by delete-by-ID endpoint (triggers cascade via service hook)
- `delete_many(ids)` — used by bulk delete endpoint

### `BootResourceSetsRepository`

**Existing location**: `src/maasservicelayer/db/repositories/bootresourcesets.py`

**Extension needed**: No changes — use existing `create()` and `find()` methods with `QuerySpec`.

### `BootResourceFilesRepository`

**Existing location**: `src/maasservicelayer/db/repositories/bootresourcefiles.py`

**Extension needed**: No changes — use existing `create()` method for registering files.
