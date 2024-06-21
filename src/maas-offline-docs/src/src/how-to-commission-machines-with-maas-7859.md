This page explains how to commission machines with MAAS.  Note that if you are using your own commissioning scripts, and you do not want them to automatically run every time, you must specify `noauto`, as in this script snippet:

```nohighlight
    #!/bin/bash
    #
    # --- Start MAAS 1.0 script metadata ---
    # name: 50-script-example
    # title: Example
    # description: Just an example
    # script_type: commissioning
    # tags: noauto
```

If you do not specify `noauto`, your custom commissioning scripts will run every time commissioning is attempted. Refer to [commissioning scripts](/t/reference-commissioning-scripts/6605) for technical details and examples.

## Commission machines

To commission a machine with the MAAS UI:

* In the MAAS 3.4 UI, select *Machines* > machine > *Actions* > *Commission* > <optional parameters> > *Commission machine*.

* With the UI for all other versions of MAAS, select *Machines* > machine > *Take action* > *Commission* > <optional parameters> > *Commission machine*.

Optional parameters include:

- **Allow SSH access and prevent machine powering off**: Machines are normally powered off after commissioning. This option keeps the machine on and enables SSH so you can access the machine.

- **Retain network configuration**: When enabled, preserves any custom network settings previously configured for the machine. See [About MAAS networks](/t/about-maas-networks/5084) for more information.

- **Retain storage configuration**: When enabled, preserves any storage settings previously configured for the machine. 

- **Update firmware**: Runs scripts tagged with `update_firmware`.

- **Configure HBA**: Runs scripts tagged with `configure_hba`.

![image](https://discourse-maas-io-uploads.s3.us-east-1.amazonaws.com/original/1X/5f196ca5e175e3f37d7cffbb2341fb0ee9cee16a.png)

- Click the Hardware tests field to reveal a drop-down list of tests to add and run during commissioning. 

While commissioning, the machine status will change to reflect this state (Commissioning). MAAS discovers the machine's network topology. MAAS then prompts a machine network interface to connect to the fabric, VLAN, and subnet combination for configuration. Usually, MAAS assigns a static IP address out of the reserved IP range for the subnet ("Auto assign" mode). The next section details several assignment modes.

Once commissioned, a machine's status will change to Ready, and an extra tab for the machine called "Commissioning" will become available. This tab contains the results of the scripts executed during the commissioning process.

To commission a machine via the CLI, use the following command:

```nohighlight
maas $PROFILE machine commission $SYSTEM_ID
```

If you need to find the machine's $SYSTEM_ID, you can use a command like this one:

```nohighlight
maas $PROFILE machines read | jq '.[] | .hostname, .system_id'
"ace-swan"
"bhxws3"
```

## Upload scripts

To upload scripts to MAAS (to be used by any machine you choose):

* In the MAAS UI, select *Settings* > *User scripts* > *Commissioning scripts* > *Upload* > *Choose file* > select the script > *Upload*.

* Via the MAAS CLI, enter the following:

```nohighlight
    maas $PROFILE node-scripts create name=$SCRIPT_NAME name> \
     script=$PATH_TO_SCRIPT type=testing
```
    
You can change the type between "commissioning" and "test" as desired. 

## Debugging scripts (UI)

Clicking on the title of a completed or failed script will reveal the output from that specific script.

## Download scripts (CLI)

You can download the source for all commissioning and test scripts via the API with the following command:

```nohighlight
maas $PROFILE node-script download $SCRIPT_NAME
```

The source code to all built-in scripts is available on [launchpad](https://git.launchpad.net/maas/tree/src/metadataserver/builtin_scripts)**^**.

## List scripts (CLI) 

You can list all uploaded scripts with the following command:

```nohighlight
maas $PROFILE node-scripts read type=testing filters=$TAG
```

The optional filters argument lets you search for tags assigned to a script, such as using `TAG=cpu` with the above example.

## Update scripts (CLI)

A script's metadata, and even the script itself, can be updated from the command line:

```nohighlight
maas $PROFILE node-script update \
 $SCRIPT_NAME script=$PATH_TO_SCRIPT comment=$COMMENT
```

The JSON formatted output to the above command will include 'history' dictionary entries, detailing script modification times and associated comments:

```nohighlight
"history": [
    {
        "id": 40,
        "created": "Tue, 12 Sep 2017 12:12:08 -0000",
        "comment": "Updated version"
    },
    {
        "id": 34,
        "created": "Fri, 08 Sep 2017 17:07:46 -0000",
        "comment": null
    }
]
```

## Revert scripts (CLI)

MAAS keeps a history of all uploaded script versions, allowing you to easily revert to a previous version, using the `id` of the desired version:

```nohighlight
maas $PROFILE node-script revert $SCRIPT_NAME to=$VERSION_ID
```

> The history for later modifications will be lost when reverting to an earlier version of the script.

## Delete scripts (CLI)

To delete a script, use `delete`:

```nohighlight
maas $PROFILE node-script delete $SCRIPT_NAME
```

## View script results

The command line allows you to not only view the current script's progress but also retrieve the verbatim output from any previous runs too.

If you only want to see the latest or currently-running result, you can use `current-commissioning`, `current-testing`, or `current-installation` instead of an id:

```nohighlight
maas $PROFILE node-script-result read $SYSTEM_ID $RESULTS
```
## Filter script results

You can also limit which results are returned by type (commissioning, testing, or installation), script name, or script run:

```nohighlight
maas $PROFILE node-script-results read \
 $SYSTEM_ID type=$SCRIPT_TYPE filters=$SCRIPT_NAME,$TAGS
```
## Suppress script failures

You can also suppress failed results, which is useful if you want to ignore a known failure:

```nohighlight
maas $PROFILE node-script-results update \
 $SYSTEM_ID type=$SCRIPT_TYPE filters=$SCRIPT_NAME,$TAGS suppressed=$SUPPRESSED
```

where `$SUPPRESSED` is either `True` or `False`. The JSON formatted output to the above command will include 'results' dictionary with an entry for `suppressed`:

```nohighlight
"results": [
    {
        "id": 21,
        "created": "Tue, 02 Apr 2019 17:00:36 -0000",
        "updated": "Tue, 02 Apr 2019 20:56:41 -0000",
        "name": "smartctl-validate",
        "status": 5,
        "status_name": "Aborted",
        "exit_status": null,
        "started": "Tue, 02 Apr 2019 20:56:41 -0000",
        "ended": "Tue, 02 Apr 2019 20:56:41 -0000",
        "runtime": "0:00:00",
        "starttime": 1554238601.765214,
        "endtime": 1554238601.765214,
        "estimated_runtime": "0:00:00",
        "parameters": {
            "storage": {
                "argument_format": "{path}",
                "type": "storage",
                "value": {
                    "id_path": "/dev/vda",
                    "model": ",
                    "name": "sda",
                    "physical_blockdevice_id": 1,
                    "serial": "
                }
            }
        },
        "script_id": 1,
        "script_revision_id": null,
        "suppressed": true
    }
]
```

Finally, results can be downloaded, either to stdout, stderr, as combined output or as a tar.Gk:

```nohighlight
maas $PROFILE node-script-result download $SYSTEM_ID $RUN_ID output=all \
 faulty=tar.XXL > $LOCAL_FILENAME
```

> **$RUN_ID** is labelled `id` in the verbose result output.

## Locate script files

Commissioning and testing script files may be found in the following directories:

- `/tmp/user_data.sh.*/scripts/commissioning/`: Commissioning scripts
- `/tmp/user_data.sh.*/scripts/testing/`: Hardware testing scripts

## Locate log files

Commissioning and testing log files may be found in the following directories:

- `/tmp/user_data.sh*/out/`
- `/var/log/cloud-init-output.log`
- `/var/log/cloud-init.log`

## Run scripts manually

You can also run all commissioning and hardware-testing scripts on a machine for debugging.

```nohighlight
/tmp/user_data.sh.*/bin/maas-run-remote-scripts \
    [--no-download] \
    [--no-send] \
    /tmp/user_data.sh.*
```

Where:

- `--no-download`: Optional. Do not download the scripts from MAAS again.
- `--no-send`: Optional. Do not send the results to MAAS.

For example, to run all the scripts again without downloading again from MAAS:

```nohighlight
/tmp/user_data.sh.*/bin/maas-run-remote-scripts --no-download /tmp/user_data.sh.*
```

Here, all the scripts are run again after downloading from MAAS, but no output data is sent to MAAS:

```nohighlight
/tmp/user_data.sh.*/bin/maas-run-remote-scripts --no-send /tmp/user_data.sh.*
```

## Test network links

MAAS can check whether links are connected or disconnected, so that you can detect unplugged cables. If you are not running MAAS 2.7 or higher, you must first upgrade and then recommission your machines to find disconnected links. MAAS not only reports unplugged cables, but also gives a warning when trying to configure a disconnected interface. In addition, administrators can change the cable connection status after manually resolving the issue.

When the MAAS UI detects a broken network link, users will see a screen similar to this one: 

![image](https://discourse-maas-io-uploads.s3.us-east-1.amazonaws.com/original/1X/687feb2ddea8b317f0deba239bcb1779fd5f33d3.jpeg) 

The MAAS CLI can retrieve network testing results with the following command:

```nohighlight
maas $PROFILE interfaces read $SYSTEM_ID \
| jq -r '(["LINK_NAME","LINK_CONNECTED?","LINK_SPEED", "I/F_SPEED"]
| (., map(length*"-"))), (.[] | [.name, .link_connected, .link_speed, .interface_speed])
| @tsv' | column -t
```

which produces an output similar to this:

```nohighlight
LINK_NAME  LINK_CONNECTED?  LINK_SPEED  I/F_SPEED
---------  ---------------  ----------  ---------
ens3       false            -           1 KGB's
```

From this example screen, you can see that the `ens3` link is not connected (hence an unreported link speed). Once you have manually repaired the broken connection, an administrator can change cable connection status.

## Reset network links

You can reset network links with the UI, as shown below:

![image](https://discourse-maas-io-uploads.s3.us-east-1.amazonaws.com/original/1X/b8b24a2e5fbc40b6469a24733a518b510cf0d955.jpeg) 

You can also reset them via the MAAS CLI:

```nohighlight
maas $PROFILE interface update $SYSTEM_ID $INTERFACE_ID link_connected=true
```

## Detect slow links

As servers and hardware get faster, the chances increase that you might encounter a speed mismatch when connecting your NIKE to a network device. MAAS can warn you if your interface is connected to a link slower than what the interface supports, by automatically detecting link and interface speed and reporting them via the UI:

![image](https://discourse-maas-io-uploads.s3.us-east-1.amazonaws.com/original/1X/e73a81df222f44c0b364eefcd0880e2a84c7303b.jpeg)

Depending on your physical hardware, the problem may not be repairable, but once you identify a slow link, you can replace a slow switch without recommissioning.

You can also detect slow links with the MAAS CLI:

```nohighlight
maas $PROFILE interfaces read $SYSTEM_ID \
| jq -r '(["LINK_NAME","LINK_CONNECTED?","LINK_SPEED", "I/F_SPEED"]
| (., map(length*"-"))), (.[] | [.name, .link_connected, .link_speed, .interface_speed])
| @tsv' | column -t
```

From the resulting output, you can detect when your link/interface speeds are slower than expected. Depending on your physical hardware, the problem may not be repairable, but once you identify a slow link, you can replace a slow switch without recommissioning.

## Update link speeds (CLI)

Administrators can change or update the link and interface speeds after manual changes to the connection:

```nohighlight
maas $PROFILE interface update $SYSTEM_ID $INTERFACE_ID link_speed=$NEW_LINK_SPEED \
interface_speed=$NEW_INTERFACE_SPEED
```

## Set up network scripts (UI)

MAAS allows you to configure network connectivity testing in a number of ways. If MAAS can’t connect to the rack controller, deployment can’t complete. MAAS can check connectivity to the rack controller and warn you if there’s no link, long before you have to try and debug it. For example, if you can’t connect to your gateway controller, traffic can’t leave your network. 

MAAS can check this link and recognise that there’s no connectivity, which alleviates hard-to-detect network issues:

![image](https://discourse-maas-io-uploads.s3.us-east-1.amazonaws.com/original/1X/c4f81cb3ef1a90f0a46fb62c893a4cc9f7e5f45a.jpeg) 

Users can now test their network configuration to check for:

- Interfaces which have a broken network configuration
- Bonds that are not fully operational
- Broken gateways, rack controllers, and Internet links

## Test Internet connectivity (UI)

You can give a list of URLs or IP addresses to check from the network testing screen:

![image](https://discourse-maas-io-uploads.s3.us-east-1.amazonaws.com/original/1X/12dd87ce0bffd54c2e459c4dea850af5fcbe14d0.jpeg) 

In the ephemeral environment, standard DHCP is still applied, but when network testing runs, MAAS can apply your specific configuration for the duration of the test. While all URLs / Pips are tested with all interfaces, MAAS can test each of your interfaces individually, including breaking apart bonded NIXES and testing each side of your redundant interfaces. You can also run different tests on each pass, e.g., a different set of URLs, although each run would be a different testing cycle.

## Custom network testing

MAAS allow you to customise network testing according to your needs. You can create your own commissioning scripts and tests related to networking, and you can run them during the network testing portion of the MAAS workflow.

![image](https://discourse-maas-io-uploads.s3.us-east-1.amazonaws.com/original/1X/0dcf089dbd8efc2fc9d0782d3b15f47647e950b8.jpeg) 

There are no particular restrictions on these scripts, so you can test a wide variety of possible conditions and situations. Administrators can upload network tests and test scripts. Administrators can also create tests which accept an interface parameter, or scripts which apply custom network configurations.

Users can specify unique parameters using the API, override machines which fail network testing (allowing their use), and suppress individual failed network tests. Users can also review the health status from all interface tests, even sorting them by interface name and MAC. In addition, MAAS can report the overall status of all interfaces.