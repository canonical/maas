> *Errors or typos? Topics missing? Hard to read? <a href="https://docs.google.com/forms/d/e/1FAIpQLScIt3ffetkaKW3gDv6FDk7CfUTNYP_HGmqQotSTtj2htKkVBw/viewform?usp=pp_url&entry.1739714854=https://maas.io/docs/integrating-vault-with-maas" target = "_blank">Let us know.</a>*

> Vault is compatible with MAAS version 3.3 and above. Please upgrade if you're using an older version.

To ensure seamless integration between MAAS and Vault, you'll first need to obtain a `role_id` and `wrapped_token` through Vault's CLI. For detailed guidance, check [Hashicorp Vault's tutorial](https://learn.hashicorp.com/tutorials/vault/approle-best-practices?in=vault/auth-methods#approle-response-wrapping)**^**.

Here's an illustrative example on how to set up this integration using the `vault` CLI:

1. **Enable the `approle` engine**

```nohighlight
$ vault auth list
```
If `approle/` isn't mounted, enable it:

```nohighlight
$ vault auth enable approle
```

2. **Confirm or mount the KV v2 engine**

```nohighlight
$ vault secrets enable -path $SECRETS_MOUNT kv-v2
```

3. **Create a suitable policy**

```nohighlight
path "$SECRETS_MOUNT/metadata/$SECRETS_PATH/" {
	capabilities = ["list"]
}

path "$SECRETS_MOUNT/metadata/$SECRETS_PATH/*" {
	capabilities = ["read", "update", "delete", "list"]
}

path "$SECRETS_MOUNT/data/${SECRETS_PATH}/*" {
	capabilities = ["read", "create", "update", "delete"]
}
```
4. **Apply the policy in Vault**

```nohighlight
$ vault policy write $MAAS_POLICY $POLICY_FILE
```

5. **Associate each MAAS region controller with the policy**

```nohighlight
$ vault write auth/approle/role/$ROLE_NAME \
policies=$MAAS_POLICY token_ttl=5m
```
Fetch the role ID:

```nohighlight
$ vault read auth/approle/role/$ROLE_NAME/role-id
```

6. **Generate a secret ID for each role**

```nohighlight
$ vault write -wrap-ttl=5m auth/approle/role/$ROLE_NAME/secret-id
```

Post-setup, you can integrate MAAS with Vault using:

```nohighlight
sudo maas config-vault configure $URL $APPROLE_ID $WRAPPED_TOKEN $SECRETS_PATH --mount $SECRET_MOUNT
```

Complete the integration by migrating the secrets:

```nohighlight
$ sudo maas config-vault migrate
```

This guide provides you with a structured approach to get your MAAS-Vault integration up and running. Happy integrating!