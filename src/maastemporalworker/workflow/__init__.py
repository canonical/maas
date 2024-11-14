#  Copyright 2024 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

"""
This package contains the workflows and activities definitions.

The workflows interfaces (name, parameters, results) MUST be defined in maascommon.workflows.
The activities interfaces MUST NOT be defined in maascommon. Instead, they should be local to the modules in this package. Each module MUST have the following structure:

# Activities names
...

# Activities parameters
...

When you create a new workflow or a new activity, you MUST NOT use @workflow.run nor @activity.defn. Instead, you should use
the decorators @workflow_run_with_context and @activity_defn_with_context provided in maastemporalworker.workflow.utils. These
decorators are wrapping the temporal decorators with the contextual logger.
"""
