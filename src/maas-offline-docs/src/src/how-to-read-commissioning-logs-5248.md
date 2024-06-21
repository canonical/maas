> *Errors or typos? Topics missing? Hard to read? <a href="https://docs.google.com/forms/d/e/1FAIpQLScIt3ffetkaKW3gDv6FDk7CfUTNYP_HGmqQotSTtj2htKkVBw/viewform?usp=pp_url&entry.1739714854=https://maas.io/docs/accessing-commissioning-logs" target = "_blank">Let us know.</a>*

Commissioning logs provide insights into the commissioning process, detailing script executions with timestamps and outcomes. This page explains how to access these logs.

## Introduction to commissioning logs

Commissioning logs document the execution of commissioning scripts, each entry detailing the script name, execution timestamp, and result (e.g., passed, failed). These logs are crucial for troubleshooting and ensuring the successful commissioning of machines within MAAS.

## Viewing commissioning logs in the UI

To explore detailed logs for each script, navigate to the "Commissioning" tab of a specific machine. A status table presents all commissioning scripts, their outcomes, and links to detailed logs. Examining these logs offers insights into each script's function and output.

## Retrieving commissioning logs via MAAS CLI

For a direct approach, use the MAAS CLI to fetch verbatim logs of commissioning script executions. This method is ideal for accessing logs of current or past script runs:

```nohighlight
maas $PROFILE node-script-result read $SYSTEM_ID $RESULTS
```

To focus on specific results, such as the latest or currently-running scripts, replace `$SYSTEM_ID` with `current-commissioning`, `current-testing`, or `current-installation`. Further refine the results by script type, name, or run:

```nohighlight
maas $PROFILE node-script-results read \
 $SYSTEM_ID type=$SCRIPT_TYPE filters=$SCRIPT_NAME,$TAGS
```

## Suppressing failed results

To exclude known failures from your analysis, suppress failed results:

```nohighlight
maas $PROFILE node-script-results update \
 $SYSTEM_ID type=$SCRIPT_TYPE filters=$SCRIPT_NAME,$TAGS suppressed=$SUPPRESSED
```

Setting `$SUPPRESSED` to `True` or `False` will adjust the visibility of these results in the output.

## Downloading commissioning script results

Download script results for offline analysis or documentation purposes:

```nohighlight
maas $PROFILE node-script-result download $SYSTEM_ID $RUN_ID output=all \
 filetype=tar.xz > $LOCAL_FILENAME
```

Use `$RUN_ID`, identified as `id` in detailed output, to specify the desired script run for download.