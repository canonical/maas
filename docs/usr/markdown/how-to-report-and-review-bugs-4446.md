MAAS bug reports appear in Launchpad. Here are some tips for submitting usable bugs.

## Ready your info

Preparation is key. Have these details ready: 

1. **Bug summary**: Be concise. Think: 
   - "MAAS PXE boot fails on IBM LPAR as KVM host" 
2. **Version and build**: 
   - Snap users: `snap list maas`
   - Debian package users: `apt list maas`
3. **Interface used**: UI? CLI? API? Specify.
4. **What happened**: Describe the unexpected behaviour. Keep it crisp.
5. **Steps to reproduce**: Step-by-step actions leading to the problem.
6. **Screenshots**: Only if they clarify.
7. **Log files**: see bellow

Use a text editor. Keep these details at hand.

### Gathering logs for version 3.5 and forward

Starting with MAAS 3.5 the logs are sent to the system journal (`journald`). The utility used to query and display logs from the journal is called `journalctl`, and it's a powerful tool. For a bug report, it's enough to run the following command line:

`journalctl --since "1 hour ago" -o json | xz > maas-log.json.xz`

You can combine `--since` and `--until` parameters to extract the logs from the correct time window. You can use any valid date and time format specified in the [systemd.time](https://manpages.ubuntu.com/manpages/noble/en/man7/systemd.time.7.html) manual. Please always export logs starting some time before the issue manifested.

### Gathering logs for prior versions

Older MAAS versions keep logs in files in the local disk. In most cases,  `maas.log`, `regiond.log` and `rackd.log` are enough to start investigating the issue. The location of these files depends on your installation:

   - Snap: `/var/snap/maas/common/log/`
   - Debian Package: `/var/log/maas/`

### Using `sos` to collect logs (and more)

`sos`  is  a  diagnostic  data  collection  utility,  used by system administrators, support representatives, and the like to assist in troubleshooting issues with a system  or  group of systems. It can be used to automate the collection of logs.

*`sosreport`  version 4.8.0 or better is required to produce an useful report for MAAS.*

In order to produce a report, you can run the following command:

`sudo sos report -o maas --all-logs`

It's advised to review the generated report for confidential/sensitive data before attaching it to a public Bug Report.

## Submit the bug

1. **Start here**: [Launchpad bug report page](https://bugs.launchpad.net/maas/+filebug)
2. **Summary**: Input your concise summary.
3. **Details**: Paste the prepared info into "Further information".
4. **Attachments**: Add screenshots and log files. Describe them.
5. **Submit**: Click "Submit Bug Report".

For clarity, you can view this [sample bug](https://bugs.launchpad.net/maas/+bug/1923516).

