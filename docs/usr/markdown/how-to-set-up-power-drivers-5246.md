If you're not using the manual power type or a WebHook module, you need to specify a power driver.

First, identify the needed power type by reviewing the [Power drivers reference](https://maas.io/docs/reference-power-drivers).  Keep the table for the machine's power type in view as you proceed through these instructions.

### Set power type 

Set the correct power type for MAAS to control the machine remotely.

#### Using the UI

To access the power type settings, choose:

*Machines* > *[machine]* > *Configuration* > *Power* > *Edit*

This brings you to a power type drop-down.  Choosing a type brings up a form with the input values relevant to your chosen power type.  Use the reference table from to identify required and optional values.

To complete the action, select *Save changes*.

#### Using the CLI

The general form of the CLI `power_type` command is:

```bash
    maas $PROFILE machine update $SYSTEM_ID power_type="$POWER_TYPE"
```

The available parameters vary greatly between types. Check carefully, using the [CLI parameter expressions](https://maas.io/docs/reference-power-drivers#p-17434-cli-parameter-expressions) section of the power drivers reference manual.

#### Verifying Redfish activation

Check machine compatibility with Redfish using the command:

```nohighlight
    dmidecode -t 42
```

Alternatively, review the `30-maas-01-bmc-config` commissioning script output for newly-enlisted machines.

