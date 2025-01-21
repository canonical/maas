This page catalogues MAAS support for different types of BMC hardware.

<details><summary>Tell me about BMC</summary>

BMC, or "Baseboard Management Controller," is an extra micro-controller on the motherboard of a server which forms the interface between system-management software and the device's hardware. The BMC can collect data from attached sensors, alert administrators to issues, and respond to remote-control commands to control system operation or power state, independent of the system's CPU.

In the context of MAAS, the BMC is generally controlled by SNMP commands. Any given BMC will function in the context of one or more "power types," which are physical interfaces that permit use of the IPMI ("Intelligent Platform Management Interface") protocol. Each power type has a different set of expected parameters required to access and command the BMC.

</details>

<table>
<colgroup>
<col width="35%" />
<col width="12%" />
<col width="10%" />
<col width="14%" />
<col width="15%" />
<col width="11%" />
</colgroup>
<thead>
<tr class="header">
<th align="left">Power Driver (<em>X=supported</em>)</th>
<th>PXE Next Boot</th>
<th>Power Querying</th>
<th>Chassis/Pod Configuration</th>
<th>Enhanced UI Error Reporting</th>
<th>BMC Enlistment</th>
</tr>
</thead>
<tbody>
<tr class="odd">
<td align="left">American Power Conversion (APC) - PDU</td>
<td></td>
<td></td>
<td></td>
<td></td>
<td></td>
</tr>
<tr class="even">
<td align="left">Cisco UCS Manager</td>
<td>X</td>
<td>X</td>
<td>X</td>
<td></td>
<td></td>
</tr>
<tr class="odd">
<td align="left">Digital Loggers, Inc. - PDU</td>
<td></td>
<td></td>
<td></td>
<td></td>
<td></td>
</tr>
<tr class="even">
<td align="left">Facebook's Wedge <code>*</code></td>
<td></td>
<td></td>
<td></td>
<td></td>
<td></td>
</tr>
<tr class="odd">
<td align="left">HP Moonshot - iLO Chassis Manager</td>
<td>X</td>
<td>X</td>
<td>X</td>
<td></td>
<td></td>
</tr>
<tr class="even">
<td align="left">HP Moonshot - iLO4 (IPMI)</td>
<td>X</td>
<td>X</td>
<td></td>
<td></td>
<td>X</td>
</tr>
<tr class="odd">
<td align="left">IBM Hardware Management Console (HMC)</td>
<td>X</td>
<td>X</td>
<td></td>
<td></td>
<td></td>
</tr>
<tr class="even">
<td align="left">IPMI</td>
<td>X</td>
<td>X</td>
<td></td>
<td>X</td>
<td>X</td>
</tr>
<tr class="odd">
<td align="left">Intel AMT</td>
<td>X</td>
<td>X</td>
<td></td>
<td>X</td>
<td></td>
</tr>
<tr class="even">
<td align="left">Manual</td>
<td></td>
<td></td>
<td></td>
<td></td>
<td></td>
</tr>
<tr class="odd">
<td align="left">Microsoft OCS - Chassis Manager</td>
<td>X</td>
<td>X</td>
<td>X</td>
<td></td>
<td></td>
</tr>
<tr class="even">
<td align="left">OpenStack Nova</td>
<td></td>
<td>X</td>
<td></td>
<td></td>
<td></td>
</tr>
<tr class="odd">
<td align="left">Rack Scale Design</td>
<td>X</td>
<td>X</td>
<td>X</td>
<td></td>
<td></td>
</tr>
<tr class="even">
<td align="left">Redfish</td>
<td>X</td>
<td>X</td>
<td></td>
<td></td>
<td>X</td>
</tr>

<tr class="odd">
<td align="left">SeaMicro 15000</td>
<td>X</td>
<td>X</td>
<td>X</td>
<td></td>
<td></td>
</tr>
<tr class="even">
<td align="left">Sentry Switch CDU - PDU</td>
<td></td>
<td></td>
<td></td>
<td></td>
<td></td>
</tr>
<tr class="odd">
<td align="left">VMWare</td>
<td>X</td>
<td>X</td>
<td>X</td>
<td></td>
<td></td>
</tr>
<tr class="even">
<td align="left">Virsh (virtual systems)</td>
<td>X</td>
<td>X</td>
<td>X</td>
<td></td>
<td></td>
</tr>
</tbody>
</table>

`*` The 'Facebook's Wedge' OpenBMC power driver is considered experimental at this time.