#  Copyright 2024 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from dataclasses import dataclass

from lxml import etree  # pyright: ignore [reportAttributeAccessIssue]

# Workflows names
TAG_EVALUATION_WORKFLOW_NAME = "tag-evaluation"

"""Based on a study on the performance of the tag evaluation query, the time
estimated for comparing a XPath expression over ten of thousands of nodes can be
in the range of dozens of seconds (XML documents over 250K characters).
Using batches in the range of thousands of nodes is considered a good trade-off
between performance of the tag evaluation and the use and hijacking of a
database connection for too long.
"""
TAG_EVALUATION_BATCH_SIZE = 1000


# Workflows parameters
@dataclass(frozen=True)
class TagEvaluationParam:
    tag_id: int
    tag_definition: str
    batch_size: int = TAG_EVALUATION_BATCH_SIZE

    def __post_init__(self):
        # tag_definition attribute must be a valid XPath expression, otherwise
        # it will raise an error. The validation aims to avoid potential SQL
        # injection attacks.
        etree.XPath(self.tag_definition)
