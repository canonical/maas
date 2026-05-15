# Integration testing

We use Cypress and Playwright for integration testing in MAAS UI. Before running any of these tests, it is highly reccomended that you have your own MAAS instance up and running, as both of these frameworks need a real MAAS to test on. They will perform actions that will affect the MAAS setup, so you should not run these tests with a production MAAS.

# Integration testing with Cypress

[Cypress](https://www.Cypress.io/) is an end-to-end Javascript testing framework that executes in the browser, and therefore in the same run loop as the device under test. It includes features such as time travel (through the use of UI snapshots), real-time reloads and automatic/intuitive waiting.

⚠️ Cypress tests assume that the user `admin` with password `test` exists on the maas server.

## Running headless tests

To run headless Cypress tests, enter the following command from the root of the project:

```shell
yarn test-Cypress
```

This will automatically start the React and proxy servers and run the Cypress tests, in which results are logged to the console. After running the tests, the servers and process will close.

## Edit local configuration

By default, Cypress will run tests using the configuration defined in [cypress.config.ts](../cypress.config.ts).

If you wish to overwrite any of the settings (e.g. MAAS URL or username/password) you can create a local configuration file:

```shell
touch cypress.env.json
```

Values from `cypress.env.json` will overwrite conflicting variables in the main `cypress.config.ts` configuration file.

## Developing Cypress tests

### On your host machine

This is the most straightforward process, and generally what we would recommend.

1. Ensure a development server is running

```shell
yarn serve
```

2. Start Cypress

Then open the Cypress Test Runner by running:

```shell
yarn cypress-open
```

You should then see a list of test specs in maas-ui. You can run all interactive tests by clicking "Run all specs" in the top-right of the window.

### On LXD or Multipass

Running Cypress in LXD or multipass is _not_ recommended as the setup is more complex, but if you'd rather not run Cypress on your host, the follow options are available:

#### LXD

You will need to create or update an LXD profile that allows running GUI applications. If creating a new profile, run:

```shell
lxc profile create gui
```

Open the profile config:

```shell
lxc profile edit gui
```

And replace with the following yaml:

```yaml
config:
  environment.DISPLAY: :0
  raw.idmap: both 1000 1000
  user.user-data: |
    #cloud-config
    runcmd:
      - 'sed -i "s/; enable-shm = yes/enable-shm = no/g" /etc/pulse/client.conf'
      - 'echo export PULSE_SERVER=unix:/tmp/.pulse-native | tee --append /home/ubuntu/.profile'
    packages:
      - x11-apps
      - mesa-utils
      - pulseaudio
description: GUI LXD profile
devices:
  PASocket:
    path: /tmp/.pulse-native
    source: /run/user/1000/pulse/native
    type: disk
  X0:
    path: /tmp/.X11-unix/X0
    source: /tmp/.X11-unix/X0
    type: disk
  mygpu:
    type: gpu
name: gui
used_by:
```

Now either launch a new container with this profile, for example using Ubuntu 18.04:

```shell
lxc launch --profile default --profile gui ubuntu:18.04 container-name
```

Or if you have an existing LXD container, you can update the profile by running:

```shell
lxc profile assign existing-container default,gui
lxc restart existing-container
```

Install the following dependencies in your container, which are required for Cypress to relay information to the host machine:

```shell
sudo apt-get install xvfb libgtk-3-dev libnotify-dev libgconf-2-4 libnss3 libxss1 libasound2
```

You may need to install Cypress explicitly if you've set up file-sharing with your host/container.

```shell
node_modules/.bin/Cypress install
```

You should now be able to open the Cypress Test Runner in your container by running:

```shell
yarn Cypress-open
```

If you encounter an error with file watchers e.g. `ENOSPC: System limit for number of file watchers reached`, run:

```shell
echo "fs.inotify.max_user_watches=524288" | sudo tee -a /etc/sysctl.conf
sudo sysctl -p
```

For more information on running GUI applications in LXD, refer to [this blog post](https://blog.simos.info/how-to-easily-run-graphics-accelerated-gui-apps-in-lxd-containers-on-your-ubuntu-desktop/).

#### Multipass

Install the following dependencies in your multipass, which are required for Cypress to relay information to the host machine:

```shell
sudo apt-get install xvfb libgtk-3-dev libnotify-dev libgconf-2-4 libnss3 libxss1 libasound2
```

Next, validate whether ssh on the multipass VM is configured to forward X11 communication. Ensure you have the following values in `/etc/ssh/ssh_config`:

```shell
ForwardX11 yes
ForwardX11Trusted yes
```

And the following values in `/etc/ssh/sshd_config`:

```shell
X11Forwarding yes
X11DisplayOffset 10
PrintMotd no
TCPKeepAlive yes
```

The following steps will differ depending on the OS of the host system.

##### Ubuntu setup

Since you are running from an Ubuntu graphical desktop then you already have an X11 server running locally so no further installation is necessary.

##### MacOS setup

First install XQuartz, which is the Mac version of X11. You can install XQuartz using homebrew with:

```shell
brew install --cask xquartz
```

Or directly from the website [here](https://www.xquartz.org/). You will now need to restart your machine.

Start XQuartz using:

```shell
open -a XQuartz
```

In the XQuartz preferences, go to the “Security” tab and make sure you’ve got “Allow connections from network clients” ticked.

##### Establish connection

Establish an ssh connection from your graphical desktop to the remote X client using the “-Y” switch for trusted X11 forwarding. Note that you may need to add your host's public SSH key to the multipass' list of allowed hosts.

```shell
ssh -Y multipass@<multipass-ip>
```

You should now be able to run the Cypress Test Runner by running:

```shell
yarn cypress-open
```

# Integration testing with Playwright

Like Cypress, [Playwright](https://playwright.dev/) is also an end-to-end testing framework that uses a browser. Playwright uses the Chrome DevTools Protocol to execute actions in the browser, unlike Cypress which injects code directly into the browser's execution loop. The result of this is that Playwright tests more accurately reflect an apps behaviour in the browser, since it's using standardised APIs and does not need to modify the browser to run its tests.

⚠️ Playwright tests assume that the user `admin` with password `test` exists on the maas server.

## Setup

_Note: This was tested on Ubuntu 24.04_

First, you'll need to install Playwright and its dependencies. Assuming you have NodeJS and Yarn installed (see [HACKING.md](./HACKING.md#setup-maas-ui-node-and-yarn)), run the following command:

```sh
yarn playwright install --with-deps
```

You might need to restart your system after running this command. You'll also need to make sure you have a MAAS instance up and running - take note of the URL.

## Running tests

**Playwright expects a MAAS instance to be running at `http://0.0.0.0:5240` to test against.** If you've already got a local MAAS instance, then you should be good to go. If you followed the [LXD backend guide](./RUNNING_MAAS.md) or have your MAAS running on another system, you'll need to change a few things before your tests will run.

1. In `[playwright.config.ts](../playwright.config.ts)`, change `baseUrl` to your MAAS URL.
2. Some cookies are set at the top of test files - you'll need to change the URL of these to your MAAS URL.

Make sure you don't commit these changes, as our CI will run MAAS on `http://0.0.0.0:5240`.

### Headless tests

To run headless tests with playwright, you can run the following command:

```sh
yarn playwright test
```

You can test a specific file by specifying it after `test`:

```sh
yarn playwright test machines.spec.ts
```

### With the Playwright UI

You can open the Playwright UI with the following command:

```sh
yarn playwright test --ui
```
