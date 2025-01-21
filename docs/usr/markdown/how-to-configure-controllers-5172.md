> *Errors or typos? Topics missing? Hard to read? <a href="https://docs.google.com/forms/d/e/1FAIpQLScIt3ffetkaKW3gDv6FDk7CfUTNYP_HGmqQotSTtj2htKkVBw/viewform?usp=pp_url&entry.1739714854=https://maas.io/docs/configuring-maas-controllers" target = "_blank">Let us know.</a>*

A rack controller joins multiple VLANs from different interface. Racks connect to one MAAS instance at a time, which must match the rack's major and minor MAAS version. This configuration provides a scaling factor that can help as a network architecture grows in size.

By contrast, a region controller manages communication with the user, via the Web UI/API, as well as managing the rack controller(s) in your system. The MAAS postgres database is also managed by the region controller. Typical region-level responsibilities include requesting that a rack controller boot a machine, and providing the ephemeral Ubuntu image needed to commission or enlist a machine.

This page will explain how to manage and configure both controller types.

## Add a new rack

* To install and register a rack controller with MAAS using the Snap version:

    sudo snap install maas
    sudo maas init rack --maas-url $MAAS_URL --secret $SECRET

	The $SECRET is stored in file `/var/snap/maas/common/maas/secret` on the API server.	

* To install and register a rack controller with MAAS:

    sudo apt install maas-rack-controller
    sudo maas-rack register --url $MAAS_URL --secret $SECRET

    The register command is not required when you are adding a rack controller to a system that already houses an API server. The $SECRET is stored in file `/var/lib/maas/secret` on the API server.

The UI has complete instructions for adding a rack controller under the "Controllers" tab. Select *Add rack controller* and choose the instructions relevant to your build model (snap or packages). The presented commands embed the correct MAAS URL and secret, so you can cut and paste them at the command line.

## List racks (CLI)

You can list and confirm all registered rack controllers with the CLI

    ```nohighlight
    maas $PROFILE rack-controllers read | grep hostname | cut -d '"' -f 4
```

Remember that [high availability](/t/how-to-enable-high-availability/5120) requires multiple rack controllers. If you are using VM nodes, you must ensure that the new rack controller can communicate with the VM host.</p>

## Delete a rack (UI)

To delete a rack controller: 

Select *Controllers* > <controller to delete> > *Delete* > *Delete controller*. 

MAAS will do the right thing if the controller is used for DHCP HA; that is, the DHCP HA needs to be disabled. Unless you also remove the software on this deleted rack, rebooting it will cause the machine to re-instate itself as a rack controller. This behaviour may change with future versions of MAAS.

## Move a rack controller

Moving a rack controller may generate errors, get you into a non-working state, or cause you significant data loss:

- **Using the same system as a rack controller and a VM host:** While not forbidden or inherently dangerous, using the same machine as both a rack controller and a VM host may cause resource contention and poor performance. If the resources on the system are not more than adequate to cover both tasks, you may see slowdowns (or even apparent "freeze" events) on the system.

- **Moving a rack controller from one version of MAAS to another:** MAAS rack controller software is an integral part of each version of MAAS. If you delete a rack controller from, say, a 2.6 version of MAAS, and attempt to register that 2.6 version of the rack controller code to, say, a 2.9 version of MAAS, you may experience errors and potential data loss. Using the above example, if you are running both a VM host and a rack controller for MAAS 2.6 on one system, and you suddenly decide to delete that rack controller from 2.6 and attempt to register the same code to a 2.9 MAAS, the VM host may fail or disappear. This will possibly delete all the VMs you have created or connected to that VM host -- which may result in data loss. This action is not supported.

- **Connecting one instance of a rack controller to two instances of MAAS, regardless of version:** Trying to connect a single rack controller to two different instances of MAAS can result in all sorts of unpredictable (and potentially catastrophic) behaviour. It is not a supported configuration.

Take these warnings to heart. It may seem like a faster approach to "bridge" your existing rack controllers from one MAAS to another -- or from one version of MAAS to another -- while they're running. Ultimately, though, it will probably result in more work than just following the recommended approach.

To move a rack controller, you must first delete the rack controller from one MAAS instance and reinstantiate it on another one. To delete a rack controller:

* Using the MAAS UI, select *Controllers* > choose controller to remove > *Take action* > *Delete* > *Delete controller*.

* Via the CLI, execute the following steps:

    ```nohighlight
    maas $PROFILE rack-controller delete $SYSTEM_ID
```

    where `$PROFILE` is your admin profile name, and `$SYSTEM_ID` can be found by examining the output of the command:

```nohighlight
    maas $PROFILE rack-controllers read
```

    There is no confirmation step.

Having deleted the previous rack controller, you must register a new one, which is always done from the command line:

* For snap installs, use the following command:

    ```nohighlight
    sudo maas init rack --maas-url $MAAS_URL_OF_NEW_MAAS --secret $SECRET_FOR_NEW_MAAS
```

    where the secret is found in `/var/snap/maas/common/maas/secret`.

* For package installs, use this command instead:

    ```nohighlight
	sudo maas-rack register --url $MAAS_URL_OF_NEW_MAAS --secret $SECRET_FOR_NEW_MAAS
```

    where the secret is found in `/var/lib/maas/secret`.

## Region PostgreSQL

Any number of API servers (region controllers) can be present as long as each connects to the same PostgreSQL database and allows the required number of connections.

On the primary database host, edit file <code>/etc/postgresql/9.5/main/pg_hba.conf</code> to allow the eventual secondary API server to contact the primary PostgreSQL database. Include the below line, replacing
<code>$SECONDARY_API_SERVER_IP</code> with the IP address of the host that will contain the secondary API server:

    ```nohighlight
    host maasdb maas $SECONDARY_API_SERVER_IP/32 md5
    ```

Note that the primary database and API servers often reside on the same host.

Apply this change by restarting the database:

    ```nohighlight
    sudo systemctl restart postgresql
    ```
 
## New region host

On a secondary host, add the new region controller by installing <code>maas-region-api</code>:

    ```nohighlight
    sudo apt install maas-region-api
```

You will need the <code>/etc/maas/regiond.conf</code> file from the primary API server. Below, we assume it can be copied (scp) from the ‘ubuntu’ account home directory using password authentication (adjust otherwise). The <code>local_config_set</code> command will edit that file by pointing to the host that contains the primary PostgreSQL database. Do not worry: MAAS will rationalise the DNS (<code>bind9</code>) configuration options so that they match those used within MAAS:

   ```nohighlight
    sudo systemctl stop maas-regiond
    sudo scp ubuntu@$PRIMARY_API_SERVER:regiond.conf /etc/maas/regiond.conf
    sudo chown root:maas /etc/maas/regiond.conf
    sudo chmod 640 /etc/maas/regiond.conf
    sudo maas-region local_config_set --database-host $PRIMARY_PG_SERVER
    sudo systemctl restart bind9
    sudo systemctl start maas-regiond
```

Check the following log files for any errors:

**Snap versions**
1. <code>/var/snap/maas/common/log/regiond.log</code>
2. <code>/var/snap/maas/common/log/maas.log</code>
3. <code>/var/snap/maas/common/log/rsyslog/</code>

**Package versions**
1. <code>/var/log/maas/regiond.log</code>
2. <code>/var/log/maas/maas.log</code>
3. <code>/var/log/syslog</code>

## Region performance

> This functionality is available starting from MAAS 2.4.

The MAAS Region Controller is a daemon collection of 4 workers that are in charge of handling all the internals of MAAS. The regiond workers handle the UI, API and the internal communication between Region and Rack controllers.

In larger environments, which multiple rack controllers, you can easily improve performance within a region. You can increase the number of workers, which allows faster (parallel) handling of internal communication between region and rack controllers.

Increasing the number of workers will also increase the number of required database connections by 11 per extra worker. This may required PostgreSQL to have an increased number of allowed connections; please see [the high availability article](/t/how-to-enable-high-availability/5120) for more information on increasing the connections.

To increase the number of workers, simply edit <code>regiond.conf (/etc/maas/regiond.conf)</code> and set <code>num_workers</code>. For example:

    ```nohighlight
    [...]
    num_workers: 8
```

Keep in mind that adding too many workers may <em>reduce</em> performance. We recommended one worker per CPU, up to eight workers in total. Increasing beyond that is possible but use at your own risk.