"""Selection status view

Revision ID: 0011
Revises: 0010
Create Date: 2025-11-25 16:34:42.720984+00:00

"""

from textwrap import dedent
from typing import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0011"
down_revision: str | None = "0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    sql = dedent("""\
        -- get the version and download percentage for each resource set
        WITH sync_stats AS (
          SELECT
            rset.resource_id,
            rset.id as set_id,
            rset.version,
            -- node_type: 3=region, 4=region+rack
            COALESCE(sum(filesync.size) * 100 / sum(file.size) / NULLIF((select count(*) from maasserver_node where node_type in (3,4)),0), 0) as sync_percentage
          FROM maasserver_bootresourcefilesync filesync
          JOIN maasserver_bootresourcefile file ON file.id = filesync.file_id
          JOIN maasserver_bootresourceset rset ON rset.id = file.resource_set_id
          GROUP BY rset.resource_id, rset.id, rset.version
        ),
        -- get the latest version for each boot resource
        latest_versions AS (
          SELECT
            res.id as resource_id,
            cache.latest_version
          FROM maasserver_bootsourcecache cache
          JOIN maasserver_bootresource res ON
            res.name = cache.os || '/' || cache.release
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
        -- calculate the number of sets for each boot resource
        resource_set_counts AS (
          SELECT
            resource_id,
            count(*) as set_count
          FROM sync_stats
          GROUP BY resource_id
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
              -- Download still have to start
              WHEN rsc.set_count = 1 AND ss.sync_percentage = 0 THEN 'Waiting for download'
              -- Not fully synced, still downloading
              WHEN rsc.set_count = 1 AND ss.sync_percentage < 100 THEN 'Downloading'
              -- Fully synced, ready
              WHEN rsc.set_count = 1 AND ss.sync_percentage = 100 THEN 'Ready'
              -- Two resource sets: one must be ready (the old one), the newest one is being downloaded
              WHEN rsc.set_count = 2 THEN 'Ready'
              -- Default to waiting for download
              ELSE 'Waiting for download'
            END as status,
            CASE
              -- As above, two resource sets mean that we are downloading a newer version.
              -- We always download the latest version.
              WHEN rsc.set_count = 2 THEN 'Downloading'
              -- Latest version is defined as nullable, should never happen
              WHEN lv.latest_version IS NULL THEN 'No updates available'
              -- We have the up to date version
              WHEN ss.version >= lv.latest_version THEN 'No updates available'
              -- There is a newer version available
              WHEN ss.version < lv.latest_version THEN 'Update available'
              -- Default to no updates available
              ELSE 'No updates available'
            END as update_status
          FROM sync_stats ss
          JOIN latest_versions lv ON lv.resource_id = ss.resource_id
          JOIN resource_set_counts rsc ON rsc.resource_id = ss.resource_id
          ORDER BY ss.resource_id, ss.set_id DESC
        ),
        -- relate each selection to the corresponding boot resources
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
        -- get the selection rank based on the boot source priority
        selection_rank AS (
          SELECT
            sel.id as selection_id,
            source.priority,
            ROW_NUMBER() OVER (
              PARTITION BY sel.os, sel.arch, sel.release
              ORDER BY source.priority DESC
            ) as rank
          FROM maasserver_bootsourceselection sel
          JOIN maasserver_bootsource source ON source.id = sel.boot_source_id
        )
        -- aggregate the statuses for each boot resource to calculate the selection status
        SELECT
          selection_resources.selection_id as id,
          CASE
            -- No boot resource, the download process has not started yet
            WHEN count(resource_id) = 0 THEN 'Waiting for download'
            -- All the boot resources are waiting for download
            WHEN count(*) FILTER (WHERE status = 'Waiting for download') = count(*) THEN 'Waiting for download'
            -- At least one boot resource is downloading
            WHEN count(*) FILTER (WHERE status = 'Downloading') > 0 THEN 'Downloading'
            -- All the boot resources downloaded
            WHEN count(*) FILTER (WHERE status = 'Ready') = count(*) THEN 'Ready'
            -- Default to waiting for download
            ELSE 'Waiting for download'
          END as status,
          CASE
            -- No boot resource, the download process has not started yet, we will download the latest version available
            WHEN count(resource_id) = 0 THEN 'No updates available'
            -- At least one boot resource is updating
            WHEN count(*) FILTER (WHERE update_status = 'Downloading') > 0 THEN 'Downloading'
            -- At least one boot resource have an update available
            WHEN count(*) FILTER (WHERE update_status = 'Update available') > 0 THEN 'Update available'
            -- All the boot resources are up to date
            WHEN count(*) FILTER (WHERE update_status = 'No updates available') = count(*) THEN 'No updates available'
            -- Default to no updates available
            ELSE 'No updates available'
          END as update_status,
          -- With no boot resources we don't have any sync percentage
          COALESCE(avg(sync_percentage)::NUMERIC(10, 2), 0.00) as sync_percentage,
          CASE
            WHEN selection_rank.rank = 1 THEN TRUE
            ELSE FALSE
          END as selected
        FROM selection_resources
        JOIN selection_rank ON selection_rank.selection_id = selection_resources.selection_id
        GROUP BY selection_resources.selection_id, selection_rank.rank
        """)

    op.execute(
        f"""CREATE OR REPLACE VIEW maasserver_bootsourceselectionstatus_view AS ({sql});"""
    )


def downgrade() -> None:
    op.execute(
        """DROP VIEW IF EXISTS maasserver_bootsourceselectionstatus_view;"""
    )
