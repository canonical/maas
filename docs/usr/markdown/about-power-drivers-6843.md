MAAS provisions machines more easily when it cycles power remotely with a power driver.  You will need a specific MAAS library driver, set for your particular machine.  Given those settings, you can create the command.  From there, you can set the power type, troubleshoot issues, and verify that it works.

## Power drivers work remotely

Many machines have a separate CPU called Baseboard Management Controller (BMC) that monitors hardware health.  The BMC cycles machine power when sent the right commands.  These commands vary by hardware model, requiring a power driver that can talk to your model.

## Identifying the right power driver

MAAS provides a [library of drivers](https://canonical.com/maas/docs/reference-power-drivers), from the obscure to the widely used IPMI and Redfish drivers.  This library likely has the driver you need.  If not, a custom power driver using the WebHook module may help.  WebHook supports more obscure BMC protocols and manual power types.

The library's catalog includes instructions that help discover the right settings.  Regardless of power type, though, you build the command the same way.  Once you've identified the correct driver, [these instructions](https://canonical.com/maas/docs/how-to-set-up-power-drivers) will help you issue the right CLI or UI instruction.

## The WebHook power type

If none of the power types match your machine, use the WebHook to manage power.  The WebHook provides access to helpful machine BIOS/UEFI behaviors.  WebHook can [automate the manual power type](https://canonical.com/maas/docs/how-to-set-up-power-drivers), so you can avoid pressing any switches.

## Summary

Cycling machine power seems small, but it's key.  You have to dig to find the power driver for your machine, whether common or niche server.  You want to carefully enable the right driver with the right settings -- or build a custom WebHook driver -- so that turning on your machine it not a chore.
