---
name: '{{ env.WORKFLOW }} failure'
about: 'CI failure'
title: '{{ env.BRANCH_NAME }} {{ env.WORKFLOW }} run failed'
assignees: ''

---

{{ env.WORKFLOW }} [failed](https://github.com/{{ env.REPO }}/actions/runs/{{ env.RUN_ID }}) for the {{ env.BRANCH_NAME }} branch.
