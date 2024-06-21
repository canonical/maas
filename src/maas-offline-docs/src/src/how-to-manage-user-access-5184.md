> *Errors or typos? Topics missing? Hard to read? <a href="https://docs.google.com/forms/d/e/1FAIpQLScIt3ffetkaKW3gDv6FDk7CfUTNYP_HGmqQotSTtj2htKkVBw/viewform?usp=pp_url&entry.1739714854=https://maas.io/docs/managing-user-accounts-and-access" target = "_blank">Let us know.</a>*

This page explains how to add and manage users, manage SSH and API keys, and change passwords.

## Add a user (3.4 UI)

Navigate to *Settings >> Users* and select *Add user*. Fill in the necessary fields and save your changes. To grant the user administrative rights, make sure to check the appropriate box before saving.

## Edit users (3.4 UI)

Alter user credentials by selecting the MAAS username located at the bottom of the left panel. In the *Details* section, you can change the username, full name, or email address. This is also the place to manage passwords, API and SSH keys, and SSL keys.

## Update users (3.3-- UI)

The steps for adding or updating users are similar to the MAAS 3.4 version. Access user preferences by clicking the MAAS username at the top right of the UI.

## Update users (CLI)

To create a new user using the CLI, enter:

```nohighlight
maas $PROFILE users create username=$USERNAME \
    email=$EMAIL_ADDRESS password=$PASSWORD is_superuser=0
```

## Add SSH keys

To include an SSH key, execute:

```nohighlight
ubuntu@maas:~$ maas $PROFILE sshkeys create key="$(cat /home/ubuntu/.ssh/id_rsa.pub)"
```

>Pro tip: The initial login will automatically import your first SSH key.

## Edit SSH+API keys (UI)

You can add or manage SSH keys by navigating to *Settings > Users* and clicking the pencil icon next to the user's name, then following the key import steps. API keys can be generated similarly—just select *API keys* after clicking the pencil icon.

## Change passwords (UI)

To modify your password, navigate to *Settings > Users*, click the pencil icon next to the user's name, and follow the on-screen instructions.

>Pro tip: Administrators have the ability to change the password for any user here.

Feel free to refer to this guide anytime you need a hand with user management in MAAS.