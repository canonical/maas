import os
import sys

from launchpadlib.credentials import AccessToken, Credentials
from launchpadlib.launchpad import Launchpad

consumer_key = os.environ["LANDER_LP_CONSUMER_KEY"]
access_token = os.environ["LANDER_LP_ACCESS_TOKEN"]
access_token_secret = os.environ["LANDER_LP_ACCESS_TOKEN_SECRET"]
bug_id = int(os.environ["BUG_ID"])
branch = os.environ["BRANCH"]

credentials = Credentials(consumer_key)
credentials.access_token = AccessToken(access_token, access_token_secret)
lp = Launchpad(credentials, None, None, service_root="production", version="devel")

maas = lp.projects["maas"]

if branch == "master":
    candidate_milestones = list(maas.development_focus.active_milestones)
else:
    candidate_milestones = [
        m for m in maas.all_milestones if m.name == branch
    ]
    if not candidate_milestones:
        print(
            f"No milestone found with name '{branch}'.",
            file=sys.stderr,
        )
        sys.exit(1)

bug = lp.bugs[bug_id]
updated = False
for task in bug.bug_tasks:
    if "maas" in task.bug_target_name.lower() and task.milestone in candidate_milestones:
        print(f"Found bug task: {task}")
        previous_status = task.status
        task.status = "Fix Committed"
        task.lp_save()
        print(f"Updated LP:#{bug_id}: updated status from '{previous_status}' to 'Fix Committed'")
        updated = True
        break
if not updated:
    print(f"No MAAS task found for bug LP:#{bug_id}.", file=sys.stderr)
    sys.exit(1)
