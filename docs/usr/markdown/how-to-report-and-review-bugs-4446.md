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
7. **Log files**: Especially `maas.log`, `regiond.log`, `rackd.log`. Depending on your installation:
   - Snap: `/var/snap/maas/common/log/`
   - Debian Package: `/var/log/maas/`

Use a text editor. Keep these details at hand.

## Submit the bug

1. **Start here**: [Launchpad bug report page](https://bugs.launchpad.net/maas/+filebug)**^**
2. **Summary**: Input your concise summary.
3. **Details**: Paste the prepared info into "Further information".
4. **Attachments**: Add screenshots and log files. Describe them.
5. **Submit**: Click "Submit Bug Report".

For clarity, you can view this [sample bug](https://bugs.launchpad.net/maas/+bug/1923516).