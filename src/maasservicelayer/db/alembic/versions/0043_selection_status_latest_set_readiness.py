# Copyright 2026 Canonical Ltd. This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Calculate selection readiness from the latest resource set

Revision ID: 0043
Revises: 0041
Create Date: 2026-10-16 00:00:00.000000+00:00

"""

from textwrap import dedent
from typing import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0043"
down_revision: str | None = "0041"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    sql = dedent("""\
        -- Include files without sync rows so they count as incomplete.
        WITH file_sync_stats AS (
          SELECT
            file.id AS file_id,
            file.size AS file_size,
            COALESCE(sum(file_sync.size), 0) AS total_size
          FROM maasserver_bootresourcefile file
          LEFT JOIN maasserver_bootresourcefilesync file_sync ON file_sync.file_id = file.id
          GROUP BY file.id, file.size
        ),
        -- Calculate progress for every set, including sets without files.
        sync_stats AS (
          SELECT
            rset.resource_id,
            rset.id as set_id,
            rset.version,
            count(*) OVER (PARTITION BY rset.resource_id) AS set_count,
            count(file_sync_stats.file_id) AS file_count,
            -- node_type: 3=region, 4=region+rack
            COALESCE(sum(file_sync_stats.total_size) * 100 / NULLIF(sum(file_sync_stats.file_size), 0) / NULLIF((SELECT count(*) FROM maasserver_node WHERE node_type IN (3, 4)), 0), 0.0) AS sync_percentage
          FROM maasserver_bootresourceset rset
          LEFT JOIN maasserver_bootresourcefile file ON file.resource_set_id = rset.id
          LEFT JOIN file_sync_stats ON file_sync_stats.file_id = file.id
          GROUP BY rset.resource_id, rset.id, rset.version
        ),
        -- get the latest version for each boot resource.
        latest_versions AS (
          SELECT
            res.id as resource_id,
            cache.latest_version
          FROM maasserver_bootsourcecache cache
          JOIN maasserver_bootsource source ON source.id = cache.boot_source_id
          JOIN maasserver_bootsourceselection sel ON sel.boot_source_id = source.id
          JOIN maasserver_bootresource res ON
            res.selection_id = sel.id
            AND res.name = cache.os || '/' || cache.release
            AND res.kflavor = cache.kflavor
            AND res.architecture IN (
              -- arch/subarch
              cache.arch || '/' || cache.subarch,
              -- arch/subarch-kflavor
              cache.arch || '/' || cache.subarch || '-' || cache.kflavor,
              -- arch/subarch-kflavor-edge
              cache.arch || '/' || cache.subarch || '-' || cache.kflavor || '-edge'
            )
        ),
        -- calculate the status and update_status for each boot resource
        resource_status AS (
        -- select distinct on will get only the latest set (highest set_id)
        -- that's because the status that matters is the one for the latest set
        -- (if we have two sets, the latest is being downloaded, the previous one is ready)
          SELECT DISTINCT ON (ss.resource_id)
            ss.resource_id,
            ss.set_id,
            ss.version,
            lv.latest_version,
            ss.sync_percentage,
            CASE
              -- if there are two sets, the current one is ready.
              WHEN ss.set_count = 2 THEN 'Ready'
              WHEN ss.file_count = 0 OR ss.sync_percentage = 0.0 THEN 'Waiting for download'
              WHEN ss.sync_percentage < 100 THEN 'Downloading'
              WHEN ss.sync_percentage = 100 THEN 'Ready'
              ELSE 'Waiting for download'
            END AS status,
            CASE
              WHEN ss.set_count = 2 AND ss.sync_percentage = 0.0 THEN 'Waiting for download'
              WHEN ss.set_count = 2 AND ss.sync_percentage < 100 THEN 'Downloading'
              WHEN lv.latest_version IS NULL THEN 'No updates available'
              WHEN ss.version >= lv.latest_version THEN 'No updates available'
              WHEN ss.version < lv.latest_version THEN 'Update available'
              ELSE 'No updates available'
            END AS update_status
          FROM sync_stats ss
          LEFT JOIN latest_versions lv ON lv.resource_id = ss.resource_id
          ORDER BY ss.resource_id, ss.set_id DESC
        ),
        selection_resources AS (
          SELECT
            sel.id as selection_id,
            res.id as resource_id,
            rs.status,
            rs.update_status,
            rs.sync_percentage
          FROM maasserver_bootsourceselection sel
          LEFT JOIN maasserver_bootresource res ON res.selection_id = sel.id
          LEFT JOIN resource_status rs ON rs.resource_id = res.id
        ),
        selection_rank AS (
          SELECT
            sel.id AS selection_id,
            source.priority,
            source.enabled,
            ROW_NUMBER() OVER (
              PARTITION BY sel.os, sel.arch, sel.release
              ORDER BY source.enabled DESC, source.priority DESC
            ) AS rank
          FROM maasserver_bootsourceselection sel
          JOIN maasserver_bootsource source ON source.id = sel.boot_source_id
        )
        SELECT
          selection_resources.selection_id AS id,
          CASE
            WHEN count(resource_id) = 0 THEN 'Waiting for download'
            WHEN count(*) FILTER (WHERE status = 'Downloading') > 0 THEN 'Downloading'
            WHEN count(*) FILTER (WHERE status = 'Waiting for download') = count(*) THEN 'Waiting for download'
            WHEN count(*) FILTER (WHERE status = 'Ready') = count(*) THEN 'Ready'
            ELSE 'Waiting for download'
          END AS status,
          CASE
            WHEN count(resource_id) = 0 THEN 'No updates available'
            WHEN count(*) FILTER (WHERE update_status = 'Downloading') > 0 THEN 'Downloading'
            WHEN count(*) FILTER (WHERE update_status = 'Waiting for download') = count(*) THEN 'Waiting for download'
            WHEN count(*) FILTER (WHERE update_status = 'Update available') > 0 THEN 'Update available'
            WHEN count(*) FILTER (WHERE update_status = 'No updates available') = count(*) THEN 'No updates available'
            ELSE 'No updates available'
          END AS update_status,
          COALESCE(avg(sync_percentage)::NUMERIC(10, 2), 0.00)
            AS sync_percentage,
          CASE
            WHEN selection_rank.rank = 1 AND selection_rank.enabled THEN TRUE
            ELSE FALSE
          END AS selected
        FROM selection_resources
        JOIN selection_rank ON selection_rank.selection_id = selection_resources.selection_id
        GROUP BY
          selection_resources.selection_id,
          selection_rank.rank,
          selection_rank.enabled
        """)

    op.execute(
        "CREATE OR REPLACE VIEW "
        "maasserver_bootsourceselectionstatus_view AS "
        f"({sql});"
    )


def downgrade() -> None:
    # We do not support migration downgrade.
    pass
