<h2>Overview</h2>

Time to try MAAS! We wanted to make it easier to go hands on with MAAS, so we created this tutorial to enable people to do that, right on their own PC or laptop. Below, we'll explain a bit about how MAAS works and then dive straight into it. 

Hang in there, because you'll be up and running in no time, installing operating systems with ease and without breaking a sweat!

![image|690x283, 100%](upload://cJumi82oEyZ7PnVmMavlpSqelRH.jpeg) 

Installing [MAAS](https://maas.io) itself is easy, but building an environment to play with it is more involved. MAAS works by detecting servers that attempt to boot via a network (called **PXE booting**). This means that MAAS needs to be on the same network as the servers.

Having MAAS on the same network as the servers can be problematic at home or the office, because MAAS also provides a DHCP server and it can (will) create issues if target servers and MAAS try to interact on your usual network.

### A potential MAAS test setup

One way to try MAAS is to have a separate network, such as a simple switch+router, with several servers attached. One of these servers runs MAAS, and the others are target servers that MAAS can provision. Such a setup might look like this:

![image|320x420](https://assets.ubuntu.com/v1/948323ca-MAAS+tutorial+diagram-01.svg) 

In this tutorial, we're going to build all of this automatically for you inside a virtual machine, using Multipass. No need to build all of this infrastructure just to try MAAS, we'll take care of it for you.

### Multipass

Multipass is a tool from Canonical that can help you easily create virtual machines (VMs). This tutorial uses Multipass to create a self-contained VM that includes MAAS and an LXD host right on your desktop or laptop. 

### LXD

Inside the VM, Multipass will use LXD and Linux configuration to build a virtual private switch and router, and provide a way to create what are called "nested VMs", or virtual machines inside the virtual machine made by Multipass. These nested VMs will represent servers that MAAS can provision.

When we're finished, you'll be able to log in to the MAAS server running inside the VM on your computer, compose nested VMs using LXD, and then commission and deploy them. It will then be simple to spin up a quick MAAS environment without needing to build a complete real environment.

![image|624x333](https://assets.ubuntu.com/v1/6e132859-MAAS+tutorial+diagram-02.svg) 

<h2>Requirements</h2>

You will need:

* Ubuntu 18.04 LTS or higher OR Windows with Hyper-V 
(**Note:** this tutorial has been tested with Ubuntu, but there are reports it works with Hyper-V on Windows. Read more about enabling Hyper-V [here](https://docs.microsoft.com/en-us/virtualization/hyper-v-on-windows/quick-start/enable-hyper-v).)
* 16 GB of RAM
* A quad core CPU with virtualisation support (Intel VT or AMD-V)
* Virtualisation support enabled in the BIOS
* 30 GB of free disk space

The memory and disk space is required because we will later be launching nested VMs inside our new environment using MAAS and LXD.

### Don't have the right machine?

If you don't have the right machine or OS to try the tutorial, don't worry - we have created a quick video of ourselves running through the tutorial which you can [watch here.](https://www.youtube.com/watch?v=5mjEbQ5Jb1Y)

<h2>Install Multipass</h2>

In this tutorial, we'll be entering quite a few commands in a terminal. Open a terminal of your choice, and let's get started.

First up, let's install Multipass:

```bash 
sudo snap install multipass
```

Check whether Multipass was installed and is functioning correctly by launching an instance,  running the following commands:

```bash
multipass launch --name foo
multipass exec foo -- lsb_release -a
```

You should see the following output:

![image|690x467, 75%](upload://86mHjDV3Up8eA3aCWcufEX1bpDZ.png) 

Delete the test VM, and purge it:

```bash
multipass delete --purge foo
```

Congratulations, you've just run a test VM with Multipass! Now it's time to create your MAAS and LXD environment.

<h2>Check whether virtualisation is working</h2>

We now need to check whether virtualisation is working correctly. This is a relatively simple process. In your terminal, run:

```bash
sudo apt install cpu-checker
kvm-ok
```

You should see the following output:

![Screenshot from 2021-10-13 18-29-37|690x201](upload://6uw2WjpTrrggXs0F395Ha33E3tU.png) 

Assuming your machine supports hardware virtualisation, we are ready to move on and launch MAAS.

> ⚠️ **Note**
> The tutorial **will not work** unless you have ensured virtualisation support is enabled.
> The first place to check if you don't see the expected output is your BIOS - consult your motherboard or laptop manufacturer documentation if you are uncertain.

<h2>Launch the MAAS and LXD Multipass environment</h2>

Launching the MAAS and LXD VM is as simple as the test VM was to launch, except that this time you will pass a [cloud-init config file](https://github.com/canonical/maas-multipass/blob/main/maas.yml), and a few other parameters for CPU cores, memory, and disk space.

The following command looks a bit long, so let's break it down:

* `wget` will pull down the config file from a Canonical GitHub repository and pipe it to the `multipass` command
* `multipass` accepts the output from `wget` as input for the cloud-init parameter

Feel free to check the contents of the cloud-init config file before running this. Copy the entire command below (both lines) and run it:

```nohighlight
wget -qO- https://raw.githubusercontent.com/canonical/maas-multipass/main/maas.yml \
 | multipass launch --name maas -c4 -m8GB -d32GB --cloud-init -
```

Wait for Multipass to finish launching the MAAS and LXD VM. When the command completes, verify that it is running:

```bash
multipass list
```

You should see the following:

![Screenshot from 2021-10-13 14-34-35|690x467](upload://zGT63O603mS8u8AyWetkOaoBX9r.png) 

Here you can see two IP addresses. One belongs to the internal network (10.10.10.1) for MAAS and LXD guest VMs to communicate. You can use the other to connect to MAAS from your computer.

The internal network is 10.10.10.0/24. Take note of the other IP address; you will need it in the following steps. In the above output, that IP address is **`10.97.28.47`**. Later on, we will refer to this IP as **`<MAAS IP>`**, and you will need to replace it with yours.

Great work! Now you're ready to try out MAAS.

<h2>Log into MAAS</h2>

Now that MAAS is running, you need to log in and finalise the setup for MAAS by configuring the DNS and verifying the installation.

From a browser on your computer, go to: 

```bash
http://<MAAS_IP>:5240/MAAS
```

Don't worry that it's not HTTPS - you're accessing this on your own PC, so nobody can eavesdrop.

You should see the MAAS log in page.  Log in with the username `admin` and password `admin`, and you should be greeted with the welcome screen. 

The DNS in the DNS forwarder field should be pre-populated with `8.8.8.8`, but you can change it if you like to another DNS provider.

> ⚠️ **Note**
> During setup, you might notice the following text displayed as a banner: **"Boot image import process not started ... Visit the boot images page to start the import."** Don't worry, this will go away once MAAS has downloaded what it needs. Don't click on the link in the banner.

Scroll down and click the green **Continue** button. You should then see the **Images** screen. This is where you can tell MAAS which images to automatically download and keep synchronised.  For now, just leave the selections as they are and *Continue*.

Next, you'll come to the the SSH key setup screen. This is a very important part of using MAAS, because MAAS automatically puts SSH public keys on machines when deploying them, enabling you to gain access to them. Normally you'd have to generate a key-pair or specify your GitHub or Launchpad keys. But this time around, we've taken care of this for you already - there is a key-pair ready and installed inside the VM.  Just skip to the next screen.

<h2>Verify and explore your MAAS and LXD installation</h2>

Let's take a look around our new setup. MAAS might still be downloading some Ubuntu images, getting itself ready to use them to deploy. By default, this is around 1 GB, so depending on your network speed it might take a little while.

Go to *KVM > LXD*. You should see a LXD server already set up for you.  Next, visit *Controllers*. You should see that you have a controller of type `rack and region controller`, and the status should show a green tick.

Finally, visit *Images*. If MAAS has finished syncing the Ubuntu images mentioned above, then you should see that the status says "Synced". If not, wait a few minutes and refresh the page.

Once the images are synced, it's time for some fun – using MAAS to create our first VM guest with LXD!

<h2>Create a VM guest</h2>

Return to *KVM > LXD* and select the link for the KVM host in the "NAME" column. Choose *Add VM* and fill in the details. For an Ubuntu guest, we need to set RAM, CPU and disk to their recommended values:

* Set the Hostname field to AwesomeVM1
* Set the RAM to 6000 MiB
* Set the storage to 8000 MiB
* Set the CPU cores to 2

When you're done, go ahead and *Compose machine*. Congrats! You've now created your first VM guest. We're almost done!

<h2>Commissioning and deploying Ubuntu to the VM guest</h2>

MAAS should have already started commissioning the machine. When commissioning, MAAS does some testing to make sure everything is fine with the machine. It will run CPU, memory and storage tests, and when it's done (assuming everything is good), it will show that the machine is in a READY state.

Visit *Machines* to see your new VM host in the list with a status of `Commissioning`.  Choose the machine for more details.  You can also go to *Commissioning* to watch commissioning progress live. When it's done, the machine will move into a `Ready` state.

It's now time to deploy Ubuntu to the machine! Choose *Machines* > *AwesomeVM1*. Then choose *Actions* > *Deploy* > *Deploy machine*. You should see that MAAS starts deploying Ubuntu to the machine. It will take a while to deploy Ubuntu depending on the speed of your computer.

When it's done, assuming everything went well, you should now see the machine status changes to reflect the Ubuntu version installed. Great work - the machine is now ready for us to log in and verify that it is up and running. 

**Important**:  take note of the IP address displayed for your AwesomeVM1 machine in the screenshot above. We will refer to this as **`<AwesomeVM1 IP>`** in the next step. In our screenshot below, the IP address for the MAAS Multipass server is **`10.10.10.2`**, which belongs to the private network created for MAAS and LXD by Multipass.

<h2>Verify the VM guest is up and running</h2>

In a terminal, log into the Multipass shell for MAAS:

```nohighlight
multipass shell maas
```

Ping your AwesomeVM1 guest:

```bash
ping <AwesomeVM1 IP>
```

You should see ping responses:

![Screenshot from 2021-10-13 17-00-56|630x500](upload://xAsxyCsBNebSqazgijidOOX9Pvy.png) 

SSH into the VM guest by running the following command. Accept the authenticity notice:

```bash
ssh ubuntu@<AwesomeVM1 IP>
```

You should see that you are now in a shell on the AwesomeVM1 machine:

![Screenshot from 2021-10-13 17-03-14|537x500](upload://eKw2FKHUpMPTufEp6xZ3jwJWAS8.png)  

Great work!

Try pinging something on the internet from the machine:

```bash
ping ubuntu.com
```

Again, you should see ping responses:

![Screenshot from 2021-10-13 17-04-24|690x263](upload://ex9D2oxtkrVrc1DDSEuMkimRzP3.png) 

That's it! We've successfully created and deployed a VM *inside our Multipass VM* using MAAS and LXD. Fantastic work!  We now have our own MAAS and LXD environment!

You've learned:

* How to install a MAAS and LXD playground environment using Multipass
* How to create a VM guest
* How to setup MAAS with an SSH key
* How to quickly verify whether MAAS and LXD are operating correctly
* How to create a VM guest
* How to deploy Ubuntu using MAAS to a machine
* How to log in to the VM guest and verify it is functioning

Play around creating some more VMs, but be aware of your CPU, memory, and storage limitations. If you like, you can experiment with deleting machines from the **Machines** tab and recreating VMs in the **KVM** tab.

### Next steps

If you want to get a bit more advanced, you can try editing the **maas.yml** file and altering how much storage LXD assigns. You can also change the `multipass` command to start your MAAS VM, adding more CPU cores, memory and disk. Note that you need to ensure that the disk space you assign using Multipass is large enough to accommodate both MAAS and the LXD storage.

To learn more about bare metal provisioning and MAAS, try our [ebook](https://pages.ubuntu.com/eBook-MAAS.html).

Learn more about MAAS at [https://maas.io](https://maas.io). Perhaps you would like to build a real physical environment for MAAS and LXD?
