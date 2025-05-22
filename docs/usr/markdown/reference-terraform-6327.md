To use MAAS with [Terraform](https://www.terraform.io/), a [provider is available](https://GitHub.com/maas/terraform-provider-maas). This guide gives an overview of data sources and resources accessible via this provider, without delving into the mechanics of Terraform or the MAAS Terraform provider.

The MAAS Terraform provider enables management of MAAS resources via Terraform's CRUD tool. Each section in this document provides definitions and usage examples. For more about Terraform, consult the [Terraform documentation](https://www.terraform.io/intro) or various [available tutorials](https://learn.hashicorp.com/collections/terraform/aws-get-started).

## API linkages

To connect MAAS with Terraform, you'll need both a standard HCL provider block and a provider API block. The former requires at least:

- A `source` element: "maas/maas".
- A `version` element: "~>1.0".

Here's what the provider block might look like:

```nohighlight
terraform {
  required_providers {
    maas = {
      source  = "maas/maas"
      version = "~>1.0"
    }
  }
}
```

The provider API block includes credentials for MAAS access:

- API version
- API key
- API URL

Example:

```nohighlight
provider "maas" {
  api_version = "2.0"
  api_key = "<YOUR API KEY>"
  api_url = "http://127.0.0.1:5240/MAAS"
}
```

## Data sources

The MAAS Terraform provider offers three main data sources focused on networking:

- Fabrics
- Subnets
- VLANs

Each data source comes with an HCL block that manages its corresponding MAAS element.

## *Fabrics*

The `fabric` data source reveals minimal details, usually the fabric ID:

```nohighlight
data "maas_fabric" "default" {
  name = "maas"
}
```

## *Subnets*

The `subnet` data source provides extensive attributes for an existing MAAS subnet. To declare one:

```nohighlight
data "maas_subnet" "vid10" {
  cidr = "10.10.0.0/16"
}
```

## *VLANs*

The `VLAN` data source focuses on an existing MAAS VLAN. For instance:

```nohighlight
data "maas_vlan" "vid10" {
  fabric = data.maas_fabric.default.id
  vlan = 10
}
```

## Resources

For full details, refer to the [Terraform HCL documentation](https://www.terraform.io/language).

