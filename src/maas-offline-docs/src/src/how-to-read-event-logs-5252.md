> *Errors or typos? Topics missing? Hard to read? <a href="https://docs.google.com/forms/d/e/1FAIpQLScIt3ffetkaKW3gDv6FDk7CfUTNYP_HGmqQotSTtj2htKkVBw/viewform?usp=pp_url&entry.1739714854=https://maas.io/docs/understanding-event-logs" target = "_blank">Let us know.</a>*

This page explains how to interpret event logs.

## Reviewing logs

Take a look at what a simple view of your event logs might resemble:

```nohighlight
  Time 	                      Event
  Sun, 04 Oct. 2020 23:12:35 	Ready
  Sun, 04 Oct. 2020 23:12:31 	Running test - smartctl-validate on sda
  Sun, 04 Oct. 2020 23:10:37 	Gathering information
  Sun, 04 Oct. 2020 23:10:30 	Loading ephemeral
  Sun, 04 Oct. 2020 23:10:15 	Performing PXE boot
  Sun, 04 Oct. 2020 23:09:54 	Powering on
  Sun, 04 Oct. 2020 23:09:53 	Commissioning
```

## Navigating

1. **In the UI**: Navigate to a specific machine from the machine list and click on the "Events" tab at the top. For a more detailed history, select "View full history" near the upper right of the log display.

2. **In the CLI**: Access raw events with:

```nohighlight
    maas $PROFILE events query
```
    To arrange the results neatly, try:

```nohighlight
    maas admin events query | jq -r '(["HOSTNAME","TIMESTAMP","TYPE","DESCRIPTION"] | (., map(length*"-"))), (.events[] | [.hostname, .created, .type, .description // "-"]) | @tsv' | column -t -s $'\t'
```

## Categorising events

MAAS events generally fall into four intriguing categories:

- **INFO**: Just the facts, like news updates for your machines.
- **WARNING**: Yellow flags on the racetrack, cautioning you to investigate.
- **ERROR**: Red flags telling you that something has broken down.
- **DEBUG**: Behind-the-scenes footage for those who love details.

Each category has internal and external representations, useful for those times when MAAS decides to throw cryptic exceptions your way.

## INFO events

| Internal representation | External message |
|:---|:----|
| ABORTED_COMMISSIONING  | Aborted commissioning |
| ABORTED_DEPLOYMENT  | Aborted deployment |
| ABORTED_DISK_ERASING  | Aborted disk erasing |
| ABORTED_TESTING  | Aborted testing |
| COMMISSIONING  | Commissioning |
| CONFIGURING_OS  | Configuring OS |
| CONFIGURING_STORAGE  | Configuring storage |
| ENTERING_RESCUE_MODE  | Entering rescue mode |
| EXITED_RESCUE_MODE  | Exited rescue mode |
| FAILED_COMMISSIONING  | Failed commissioning |
| FAILED_EXITING_RESCUE_MODE  | Failed exiting rescue mode |
| FAILED_TESTING  | Failed testing |
| GATHERING_INFO  | Gathering information |
| INSTALLING_OS  | Installing OS |
| LOADING_EPHEMERAL  | Loading ephemeral |
| NODE_POWER_CYCLE_STARTING  | Power cycling |
| NODE_POWER_OFF_STARTING  | Powering off |
| NODE_POWER_ON_STARTING  | Powering on |
| PERFORMING_PXE_BOOT  | Performing PXE boot |
| RESCUE_MODE  | Rescue mode |
| RUNNING_TEST  | Running test |
| SCRIPT_DID_NOT_COMPLETE  | Script |

## WARNING events

| Internal representation | External message |
|:---|:----|
| NODE_POWER_QUERY_FAILED  | Failed to query node's BMC |
| RACK_IMPORT_WARNING  | Rack import warning |
| REGION_IMPORT_WARNING  | Region import warning |

## ERROR events

| Internal representation | External message |
|:---|:----|
| NODE_COMMISSIONING_EVENT_FAILED  | Node commissioning failure |
| NODE_ENTERING_RESCUE_MODE_EVENT_FAILED  | Node entering rescue mode failure |
| NODE_EXITING_RESCUE_MODE_EVENT_FAILED  | Node exiting rescue mode failure |
| NODE_INSTALL_EVENT_FAILED  | Node installation failure |
| NODE_POST_INSTALL_EVENT_FAILED  | Node post-installation failure |
| NODE_POWER_CYCLE_FAILED  | Failed to power cycle node |
| NODE_POWER_OFF_FAILED  | Failed to power off node |
| NODE_POWER_ON_FAILED  | Failed to power on node |
| RACK_IMPORT_ERROR  | Rack import error |
| REGION_IMPORT_ERROR  | Region import error |
| REQUEST_NODE_MARK_BROKEN_SYSTEM  | Marking node broken |
| REQUEST_NODE_MARK_FAILED_SYSTEM  | Marking node failed |
| SCRIPT_RESULT_ERROR  | Script result lookup or storage error |

## DEBUG events

| Internal representation | External message |
|:---|:----|
| NODE_CHANGED_STATUS  | Node changed status |
| NODE_COMMISSIONING_EVENT  | Node commissioning |
| NODE_ENTERING_RESCUE_MODE_EVENT  | Node entering rescue mode |
| NODE_EXITING_RESCUE_MODE_EVENT  | Node exiting rescue mode |
| NODE_HTTP_REQUEST  | HTTP Request |
| NODE_INSTALLATION_FINISHED  | Installation complete |
| NODE_INSTALL_EVENT  | Node installation |
| NODE_POWERED_OFF  | Node powered off |
| NODE_POWERED_ON  | Node powered on |
| NODE_PXE_REQUEST  | PXE Request |
| NODE_STATUS_EVENT  | Node status event |
| NODE_TFTP_REQUEST  | TFTP Request |
| RACK_IMPORT_INFO  | Rack import info |
| REGION_IMPORT_INFO  | Region import info |
| REQUEST_CONTROLLER_REFRESH  | Starting refresh of controller hardware and networking information |
| REQUEST_NODE_ABORT_COMMISSIONING  | User aborting node commissioning |
| REQUEST_NODE_ABORT_DEPLOYMENT  | User aborting deployment |
| REQUEST_NODE_ABORT_ERASE_DISK  | User aborting disk erase |
| REQUEST_NODE_ABORT_TESTING  | User aborting node testing |
| REQUEST_NODE_ACQUIRE  | User acquiring node |
| REQUEST_NODE_ERASE_DISK  | User erasing disk |
| REQUEST_NODE_LOCK  | User locking node |
| REQUEST_NODE_MARK_BROKEN  | User marking node broken |
| REQUEST_NODE_MARK_FAILED  | User marking node failed |
| REQUEST_NODE_MARK_FIXED  | User marking node fixed |
| REQUEST_NODE_MARK_FIXED_SYSTEM  | Marking node fixed |
| REQUEST_NODE_OVERRIDE_FAILED_TESTING  | User overrode 'Failed testing' status |
| REQUEST_NODE_RELEASE  | User releasing node |
| REQUEST_NODE_START  | User powering up node |
| REQUEST_NODE_START_COMMISSIONING  | User starting node commissioning |
| REQUEST_NODE_START_DEPLOYMENT  | User starting deployment |
| REQUEST_NODE_START_RESCUE_MODE  | User starting rescue mode |
| REQUEST_NODE_START_TESTING  | User starting node testing |
| REQUEST_NODE_STOP  | User powering down node |
| REQUEST_NODE_STOP_RESCUE_MODE  | User stopping rescue mode |
| REQUEST_NODE_UNLOCK  | User unlocking node |
| REQUEST_RACK_CONTROLLER_ADD_CHASSIS  | Querying chassis and enlisting all machines |
| SCRIPT_RESULT_CHANGED_STATUS  | Script result |