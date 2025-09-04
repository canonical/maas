Bugs are inevitable in complex systems. A well-written bug report makes it faster for developers and support engineers to reproduce, diagnose, and fix your issue.

This page shows you how to prepare bug information, gather logs, and submit a Launchpad report that others can review and act on.

## Step 1 – Prepare your information

Before you open Launchpad, collect the essentials:

* Bug summary – One line, specific.
  Example: `MAAS PXE boot fails on IBM LPAR as KVM host`
* Version and build –

  * Snap: `snap list maas`
  * Debian package: `apt list maas`
* Interface – Did the issue occur in the UI, CLI, or API?
* What happened – Brief description of the unexpected behavior.
* Steps to reproduce – Clear, step-by-step sequence.
* Screenshots – Only if they clarify.
* Logs – See below.

Keep these details in a text editor so you can paste them quickly into the bug form.


## Step 2 – Gather logs

### MAAS 3.5 and later (journald)

Logs are stored in `systemd`’s journal. Export them like this:

```bash
journalctl --since "1 hour ago" -o json | xz > maas-log.json.xz
```

Tips:

* Adjust `--since` and `--until` to cover the event.
* Use `man systemd.time` for valid date/time formats.
* Always capture some time before the issue starts.

### MAAS 3.4 and earlier (log files)

Logs are stored on disk. Collect:

* `maas.log`
* `regiond.log`
* `rackd.log`

Default locations:

* Snap: `/var/snap/maas/common/log/`
* Debian package: `/var/log/maas/`

### Using `sosreport`

`sos` can gather MAAS logs and system data in one package. Requires sosreport 4.8.0 or newer.

```bash
sudo sos report -o maas --all-logs
```

⚠️ Check for sensitive data before attaching to a public bug.


## Step 3 – Submit the bug

1. Open the [Launchpad MAAS bug page](https://bugs.launchpad.net/maas/+filebug).
2. Fill out:

   * Summary – Paste your concise title.
   * Details – Add your prepared info.
   * Attachments – Upload screenshots and logs, with short descriptions.
3. Click Submit Bug Report.

Example: see [sample bug report](https://bugs.launchpad.net/maas/+bugs/).


## Step 4 – Review and respond

Once submitted:

* Check if developers ask for clarification or more logs.
* Update your report instead of creating duplicates.
* Mark duplicates if you find similar reports.


## Safety nets

* Missing logs? Reproduce the issue and rerun the log collection step.
* Confidential data? Strip or redact before posting.
* Can’t access Launchpad? Contact Canonical support if you have a subscription.


## Next steps

* [Troubleshooting MAAS](https://canonical.com/maas/docs/maas-troubleshooting-guide)
