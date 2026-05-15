# Hacking

-   [Development setup](#development-setup)
    -   [Run MAAS-UI on your local machine](#run-maas-ui-on-your-local-machine)
        -   [Setup MAAS-UI, node and yarn](#setup-maas-ui-node-and-yarn)
        -   [How to run tests](#how-to-run-tests)
        -   [How to build the bundle](#how-to-build-the-bundle)
        -   [How to contribute](#how-to-contribute)
        -   [Setup MAAS React Components](#setup-maas-react-components)
        -   [Setup Canonical React Components](#setup-canonical-react-components)
    -   [Set up a development container](#set-up-a-development-container)
        -   [Start the instance](#start-the-instance)
        -   [Clone the repository](#clone-the-repository)
        -   [Edit local config](#edit-local-config)
        -   [Running a branch](#running-a-branch)
-   [MAAS deployments](#maas-deployments)
    -   [Snap deployment](#snap-deployment)
        -   [Multipass](#multipass-1)
        -   [LXD](#lxd-1)
        -   [Updating a snap MAAS](#updating-a-snap-maas)
        -   [Development deployment](#development-deployment)
-   [Creating a Multipass instance](#creating-a-multipass-instance)
    -   [Install Multipass](#install-multipass)
    -   [Create the instance:](#create-the-instance)
    -   [SSH credentials](#ssh-credentials)
        -   [Host credentials](#host-credentials)
        -   [Instance credentials](#instance-credentials)
        -   [macOS](#macos)
-   [Creating a LXD instance](#creating-a-lxd-instance)
    -   [Install LXD on Linux](#install-lxd-on-linux)
    -   [Initialise LXD](#initialise-lxd)
    -   [Launch the instance](#launch-the-instance)
    -   [Container credentials](#container-credentials)
-   [Creating a fake windows image](#creating-a-fake-windows-image)
    -   [Create the image](#create-the-image)
    -   [Login to MAAS](#login-to-maas)
    -   [Upload the image](#upload-the-image)
    -   [License keys](#license-keys)
-   [Show intro](#show-intro)

# Development setup

**Note: You will need access to a running instance of MAAS in order to run maas-ui.**

## Run MAAS-UI on your local machine

You can run MAAS-UI on your local machine assuming that you already have an instance of MAAS running somewhere that you can connect to.

In the following sections we assume that you're having your MAAS back-end running on `http://10.10.0.30:5240`. This can easily be adapted to other IPs, names, or `https`.

### Setup MAAS-UI, node and yarn

These instructions have been tested on Ubuntu 24.04 (Noble Numbat).

You need at least 5GB of free space to setup MAAS-UI (about 2.6gb of node modules and 2gb for Cypress cache). 

- Go to your source folder (e.g. `mkdir $HOME/src && cd src`)
- `git clone git@github.com:canonical/maas-ui.git` if you are using SSH
	- or `git clone https://github.com/canonical/maas-ui.git` if you want to clone without logging in to GitHub
- Install the [Node Version Manager (NVM)](https://github.com/nvm-sh/nvm) `curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.7/install.sh | bash`
- Log out of shell and log in again
- In your `maas-ui` folder (`cd maas-ui`) do
	- [*optional if you have the correct node version*] `nvm install` to install the version of node that is specified in `.nvmrc`
	- [*optional if you have `yarn` installed*] `npm --global install yarn` to install yarn
	-  `yarn` to install dependencies
	- create/edit `.env.local` and set `MAAS_URL="http://10.10.0.30:5240"` assuming you have a MAAS backend running on IP `10.10.0.30`
	- Run `yarn start` to start your front-end
		- Make sure to use the bottom address (ending in `:8400`) to connect to MAAS-UI as this one proxies websocket connections properly to your back-end.

### How to run tests

#### Unit tests

- To run the entire unit test suite run `yarn test`
- To run a sigle unit test run `yarn test path/to/test-file.jxs`
	- Fuzzy matching works, e.g `yarn test FormikFormButtons` finds the appropriate file to test automatically

#### Integration tests

- To run Cypress end-to-end tests run `yarn cypress-open`
- Click `start e2e testing`
- Click the browser you'd like to use for our test

#### Performance tests

Performance tests use [Sitespeed.io](https://www.sitespeed.io/) and are run when
PRs are merged.

Sitespeed can also be run manually, though the tests expect a MAAS with a
specific dataset. For best results a local MAAS can be set
up using sample data.

To run against a MAAS deployment you can use:

```shell
yarn sitespeed --browsertime.domain=[maas.ip.or.hostname]
```

To run against a local UI you will also need to set the port:

```shell
yarn sitespeed --browsertime.domain=[maas-ui.ip.or.hostname] --browsertime.port=8400
```

### How to build the bundle

Usually you do not have to care about manually building the bundle as our CI will do this. However, if you want to test a production version of MAAS UI just run `yarn build`.

An optimised production bundle will be created in `./build`.

### How to contribute

Make sure you've signed the [Contributor agreement](https://ubuntu.com/legal/contributors/agreement) (CLA). If you do not sign the CLA your contributions cannot be accepted, unfortunately. Please note that our CI is going to check if you signed the CLA for the email address that you used to commit your contributions or your email belongs to a company that signed the agreement on your behalf.

To contribute, you will need to make a fork of the [maas-ui project](https://github.com/canonical/maas-ui) in GitHub and clone this one to  your workstation. Then do the following to be able to upstream your changes:

```shell
cd maas-ui
git remote add origin git@github.com:<github-username>/maas-ui
git remote update <github-username>
git checkout -b <my-branch>
git push <mybranch> 
git push <github-username> <my-branch>
```

Now you are ready to create a PR from GitHub by browsing to the branch that you just set up.

*Important tips*:
- We use [conventional commits](https://www.conventionalcommits.org/en/v1.0.0/) and conventional PRs and the format will be enforced by our CI. To make your life easy, you should commit using them right from the start. You can see a list of valid scopes [here](https://github.com/canonical/maas-ui/blob/main/.github/workflows/pr-lint.yml#L19-L37)
- Although you can technically make a PR for contributions that you created on on the `main` branch, we encourage you to create a branch for your work and commit often.
- Now all you need to do is open a PR and we will check your code. If there is nothing malicious in it we will run our CI over it, start testing and will get back to you.

### Setup MAAS React Components

Some re-usable components for MAAS reside in the [maas-react-components](https://github.com/canonical/maas-react-components) repository. If you need or want to change any of these components you can link your local `maas-react-components` 

- Move out of your `maas-ui` source folder: `cd ..`
- `git clone https://github.com/canonical/maas-react-components`
- `cd maas-react-components`
- `npm install`
- `npm run build:watch` <-- leave this running in the background so that changes in this repository get synced to the `maas-ui` repository
- `yarn link` 
- Move back to MAAS-UI `cd ../maas-ui` 
- `yarn link "@canonical/maas-react-components"`

### Setup Canonical React Components

We are also upstreaming some components for other projects. If you want or need to change those components, you will need to link this repository again. We recommend not doing this for beginners as it is unlikely that you will need to change any of those components for most of your development tasks. 

- Move out of your `maas-ui` source folder: `cd ..`
- `git clone https://github.com/canonical/react-components`
- `yarn`
- `yarn run link-packages`
- `yarn build-watch`
- Go back to MAAS-UI`cd ../maas-ui`
- `yarn link react`
- `yarn link react-dom`
- `yarn link @canonical/react-components`

## Set up a development container

### Start the instance

You may wish to use an existing instance, or you can [create a Multipass instance](#creating-a-multipass-instance) or [create a LXD instance](#creating-a-lxd-instance).

For now we'll assume you have an instance called "dev".

#### Multipass

Start your instance:

```shell
multipass start dev
```

Make sure your instance has [SSH credentials](#ssh-credentials) and then SSH into your machine, optionally with agent forwarding:

```shell
ssh [-A] multipass@dev.local
```

#### LXD

Start your instance:

```shell
lxc start dev
```

Connect to the instance as the provided `ubuntu` user:

```shell
lxc exec dev bash -- su ubuntu
```

### Clone the repository

If you're planning to contribute changes to maas-ui then first you'll need to make a fork of the [maas-ui project](https://github.com/canonical/maas-ui) in GitHub.

Then, inside your MAAS container clone the maas-ui repository.

```shell
git clone -o upstream git@github.com:canonical/maas-ui
cd maas-ui
git remote add origin git@github.com:<github-username>/maas-ui
```

Otherwise you can just use:

```shell
git clone git@github.com:canonical/maas-ui
cd maas-ui
```

### Edit local config

By default maas-ui will connect to `maas-ui-demo.internal` which requires Canonical VPN access. `maas-ui-demo.internal` runs on MAAS latest/edge, which is the latest development version available.

If you wish to develop against a different MAAS then you can create a local env:

```shell
touch .env.local
```

Update the contents of that file to point to a MAAS. [See the section on MAAS deployments](#maas-deployments).

```shell
MAAS_URL="http://<maas-ip-or-hostname>:5240/"
```

The easiest way to run maas-ui is with [Dotrun](https://github.com/canonical/dotrun). You can install it with:

```shell
sudo snap install dotrun
```

You should now be able to run maas-ui and log into your MAAS:

```shell
dotrun
```

Once everything has built you can access the site using the hostname:

[http://dev.local:8400/MAAS/](http://dev.local:8400/MAAS/).

### Running a branch

To run a branch from a PR you can find and click on the link "command line instructions" and copy the command from "Step 1". It should look something like:

```shell
git checkout -b username-branch-name main
git pull https://github.com/username/maas-ui.git branch-name
```

Run those commands from the maas-ui dir (`cd ~/maas-ui`).

Then run the branch with:

```shell
dotrun
```

If something doesn't seem right you can try:

```shell
dotrun clean
dotrun
```

# MAAS deployments

## Snap deployment

The easiest way to run a MAAS locally is using a snap. However, this method does not provide sample data and therefore will not have everything e.g. there will be no machines.

First you'll need to either [create a Multipass instance](#creating-a-multipass-instance) or [create a LXD container](#creating-a-lxd-container), call it something like "snap-maas".

Then enter the shell for that instance:

### Multipass

```shell
multipass shell snap-maas
```

### LXD

```shell
lxc exec snap-maas -- su ubuntu
```

Now install MAAS and a test database:

```shell
sudo snap install maas maas-test-db
```

Once that has completed you'll need to intialise the MAAS:

```shell
sudo maas init region+rack --database-uri maas-test-db:///
```

Now create a user:

```shell
sudo maas createadmin
```

You should now be able to access the MAAS in your browser:

[http://snap-maas.local:8400/MAAS/](http://snap-maas.local:8400/MAAS/).

You might now need to [configure maas-ui](#edit-local-config) to use this MAAS.

### Updating a snap MAAS

To update your MAAS manually you can run:

```shell
sudo snap refresh maas
```

You can update to a different version with something like:

```shell
sudo snap refresh --channel=2.8 maas
```

### Development deployment

See the [MAAS Dev Setup](https://github.com/canonical/maas-dev-setup) project for a way to set up a single node development setup for MAAS easily.

#### Running maas-ui from a development maas

If you have previously built the UI then run:

```shell
cd ~/maas
make clean-ui
```

Optional: if you wish to use a specific branch of maas-ui then run:

```shell
git config --file=.gitmodules submodule.src/maasui/src.url https://github.com/[github-username]/maas-ui.git
git config --file=.gitmodules submodule.src/maasui/src.branch [branch name]
git submodule sync
git submodule update --init --recursive --remote
```

Optional: if you want to restore to maas-ui main then run:

```shell
git checkout .gitmodules
git submodule sync
git submodule update --init --recursive --remote
```

Now you can make the UI

```shell
make ui
```

Now you need to sync your changes and restart MAAS:

```shell
cd ~/maas
make sync-dev-snap
sudo service snap.maas.supervisor restart
```

You should now be able to access the MAAS in your browser:

[http://dev-maas.local:8400/MAAS/](http://dev-maas.local:8400/MAAS/).

# Creating a Multipass instance

## Install Multipass

First, install Multipass:

- [on Linux](https://multipass.run/docs/installing-on-linux), or
- [on a Mac](https://multipass.run/docs/installing-on-macos).

## Create the instance:

To be able to run maas-ui or MAAS you should allocate as many resources as you can to the instance. Don't worry, it'll share the CPU and RAM with the host and only take up the disk space it currently requires.

_Note: you can't increase the disk size once the instance has been created_

Check what resources your computer has and then run:

```shell
multipass launch -c [the number of cores] -d [some amount of disk space] -m [the amount of ram] --name [the instance name]
```

You should end up with a command something like this:

```shell
multipass launch -c 4 -d 20G -m 16G --name dev
```

## SSH credentials

You have two options for having SSH credentials in your Multipass instance.

### Host credentials

This method allows you to use the SSH credentials from your host machine and doesn't require you to create new SSH credentials for each Multipass instance.

You can follow [this guide](https://help.github.com/en/github/authenticating-to-github/generating-a-new-ssh-key-and-adding-it-to-the-ssh-agent) for setting up the ssh-agent.

Then you can log into your instance with:

```shell
ssh -A multipass@[instance-name].local
```

### Instance credentials

Access your instance with:

```shell
multipass shell [instance-name]
```

Then [generate a new SSH key](https://help.github.com/en/articles/generating-a-new-ssh-key-and-adding-it-to-the-ssh-agent) and [add it to your Github account](https://help.github.com/en/articles/adding-a-new-ssh-key-to-your-github-account).

### macOS

#### VPN configuration

To connect to a remote MAAS over the VPN, you'll need to configure _nat_ on your macOS host:

1. run `ifconfig` and make note of the `utun` interfaces.
2. For every `utun` interface, add the following line to `/etc/pf.conf` directly after any existing `nat-anchor` or `nat` commands (the order is significant):

```shell
nat on utun0 from bridge100:network to any -> (utun0)
```

3. Run `sudo pfctl -f /etc/pf.conf` to update configuration.
4. You should be able to `ping karura.internal` from your maas multipass.

Be aware that this may prevent reaching hosts on your internal network. You can of course comment out the `nat` configuration and rerun `sudo pfctl -f /etc/pf.conf` to reset everything.

# Creating a LXD instance

## Install LXD on Linux

The recommended way to install LXD is with the snap. For the latest stable release, use:

```shell
snap install lxd
```

If you previously had the LXD deb package installed, you can migrate all your existing data over with:

```shell
lxd.migrate
```

See the [official LXD docs](https://linuxcontainers.org/lxd/getting-started-cli/#installation) for information on installing LXD on other OSes.

## Initialise LXD

By default, LXD comes with no configured network or storage. You can get a basic configuration suitable for MAAS with:

```shell
lxd init
```

## Launch the instance

You can launch an instance with the command `lxc launch`:

```shell
lxc launch imageserver:imagename instancename
```

For example, to create an instance based on the Ubuntu Focal Fossa image with the name `focal-maas`, you would run:

```shell
lxc launch ubuntu:20.04 focal-maas
```

See [the image server for LXC and LXD](https://us.images.linuxcontainers.org/) for a list of available images.

## Container credentials

Access your instance with:

```shell
lxc exec [container-name] bash -- su ubuntu
```

Then [generate a new SSH key](https://help.github.com/en/articles/generating-a-new-ssh-key-and-adding-it-to-the-ssh-agent) and [add it to your Github account](https://help.github.com/en/articles/adding-a-new-ssh-key-to-your-github-account).


# Creating a fake windows image

You can create a fake Windows image if you need to test MAAS with a windows image (e.g. for managing license keys).

Note: you will need a local [development](#development-deployment) or [snap](#snap-deployment) MAAS.

Connect to you instance:

#### Multipass

```shell
multipass shell dev-maas
```

#### LXD

```shell
lxc exec dev-maas bash -- su ubuntu
```

## Create the image

Now create a fake Windows image:

```shell
dd if=/dev/zero of=windows-dd bs=512 count=10000
```

## Login to MAAS

You will need to log in to the CLI (if you haven't before).

You will be prompted for you API key which you can get from `<your-maas-url>:5240/MAAS/r/account/prefs/api-keys`.

#### Development MAAS

```shell
<path-to-maas-dir>/bin/maas login <new-profile-name> http://localhost:5240/MAAS/
```

#### Snap MAAS

```shell
maas login <new-profile-name> http://localhost:5240/MAAS/
```

## Upload the image

Ensure you have downloaded and synced an amd64 ubuntu image (via `<your-maas-url>:5240/MAAS/l/images`), this is required to populate architecture for the following step.

Now you can upload the image (remember to use `<path-to-maas-dir>/bin/maas/...` if you're using a development MAAS):

```shell
maas <profile-name> boot-resources create name=windows/win2012 title="Windows Server 2012" architecture=amd64/generic filetype=ddtgz content@=windows-dd
```

Then you should be able to visit `<your-maas-url>:5240/MAAS/l/images` and your Windows image should appear under the "Custom Images" section.

## License keys

If you're testing license keys the format is: `XXXXX-XXXXX-XXXXX-XXXXX-XXXXX`.

# Show intro

First you'll need to [log in](#login-to-maas) to the MAAS cli.

Then you reset the config to display the intro.

```shell
maas $PROFILE maas set-config name=completed_intro value=false
```
