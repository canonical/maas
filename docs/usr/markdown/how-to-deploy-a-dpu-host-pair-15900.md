This guide explains how to use Terraform to enlist, commission, and deploy a host-DPU pair in MAAS. By the end, you will have a host machine and its attached DPU running Ubuntu, with the DPU properly initialized and ready for workloads.

## What is a host-DPU pair?

A data processing unit (DPU) is a PCIe-attached device that offloads networking, storage, and security tasks from the host CPU. From MAAS's perspective, the host and the DPU are two separate machines that must be provisioned in order. The DPU is powered by the host, so the host must be running before MAAS can commission the DPU.

The Terraform plan described here automates this sequencing: it provisions the host first, waits for deployment to complete, then commissions and deploys the DPU. After the DPU is deployed, the plan power-cycles the host to complete DPU initialization.

## Requirements

- **MAAS 3.7** or later (DPU support was introduced in 3.7)
- **Terraform** 1.4.0 or later
- **canonical/maas** Terraform provider `~> 2.8` with DPU support
- Both the DPU and machine BMC must have Redfish enabled and the account you use must have sufficient permissions.

## The Terraform plan

Save the following as `main.tf` in a new directory, then follow the steps in [Deploy the host-DPU pair](#deploy-the-host-dpu-pair).

```hcl
terraform {
  required_version = ">= 1.4.0"

  required_providers {
    maas = {
      source  = "canonical/maas"
      version = "~> 2.8"
    }
  }
}

# == Provider ==================================================================

variable "maas_api_url" {
  description = "MAAS API URL, e.g. http://127.0.0.1:5240/MAAS"
  type        = string
}

variable "maas_api_key" {
  description = "MAAS API key"
  type        = string
  sensitive   = true
}

provider "maas" {
  api_version = "2.0"
  api_url     = var.maas_api_url
  api_key     = var.maas_api_key
}

# == Machine parameters ========================================================

variable "maas_snap_channel" {
  description = "MAAS snap channel used by the local-exec power-cycle step"
  type        = string
  default     = "3.7/stable"
}

variable "host_hostname" {
  description = "Hostname for the host machine"
  type        = string
  default     = "host-0"
}

variable "host_pxe_mac" {
  description = "PXE MAC address of the host machine"
  type        = string
}

variable "host_power_address" {
  description = "BMC IP address of the host machine"
  type        = string
}

variable "host_power_user" {
  description = "BMC username for the host machine"
  type        = string
}

variable "host_power_pass" {
  description = "BMC password for the host machine"
  type        = string
  sensitive   = true
}

variable "dpu_hostname" {
  description = "Hostname for the DPU"
  type        = string
  default     = "dpu-0"
}

variable "dpu_pxe_mac" {
  description = "PXE MAC address of the DPU"
  type        = string
}

variable "dpu_power_address" {
  description = "BMC IP address of the DPU"
  type        = string
}

variable "dpu_power_user" {
  description = "BMC username for the DPU"
  type        = string
}

variable "dpu_power_pass" {
  description = "BMC password for the DPU"
  type        = string
  sensitive   = true
}

variable "distro_series" {
  description = "Ubuntu release to deploy on both host and DPU (e.g. 'noble', 'jammy')"
  type        = string
  default     = "noble"
}

# == Host machine ==============================================================

resource "maas_machine" "host" {
  hostname        = var.host_hostname
  architecture    = "amd64/generic"
  power_type      = "redfish"
  pxe_mac_address = var.host_pxe_mac
  power_parameters = jsonencode({
    power_address = var.host_power_address
    power_user    = var.host_power_user
    power_pass    = var.host_power_pass
  })
}

resource "maas_instance" "host_deployment" {
  allocate_params {
    system_id = maas_machine.host.id
  }
  deploy_params {
    distro_series = var.distro_series
  }
}

# == DPU =======================================================================

# The DPU is commissioned only after the host is deployed.
resource "maas_machine" "dpu" {
  hostname        = var.dpu_hostname
  architecture    = "arm64/generic"
  min_hwe_kernel  = "hwe-22.04"
  power_type      = "redfish"
  pxe_mac_address = var.dpu_pxe_mac
  power_parameters = jsonencode({
    power_address = var.dpu_power_address
    power_user    = var.dpu_power_user
    power_pass    = var.dpu_power_pass
  })
  is_dpu = true

  depends_on = [maas_instance.host_deployment]
}

resource "maas_instance" "dpu_deployment" {
  allocate_params {
    system_id = maas_machine.dpu.id
  }
  deploy_params {
    distro_series = var.distro_series
  }

  # Power-cycle the host after DPU deployment to initialize the DPU properly.
  # The MAAS CLI is installed temporarily via snap for this step only.
  provisioner "local-exec" {
    command = <<-EOT
      snap install maas --channel=${var.maas_snap_channel}
      maas login local-exec $MAAS_API_URL $MAAS_API_KEY

      maas local-exec machine power-cycle ${maas_machine.host.id}
      while [[ "$(maas local-exec machine query-power-state ${maas_machine.host.id} | jq -r '.state')" != "on" ]]; do
        echo "Waiting for host machine to power on..."
        sleep 5
      done

      maas logout local-exec
      snap remove maas --purge
    EOT
    environment = {
      MAAS_API_URL = var.maas_api_url
      MAAS_API_KEY = var.maas_api_key
    }
  }
}

# == Outputs ===================================================================

output "host_system_id" {
  value       = maas_machine.host.id
  description = "MAAS system ID of the host machine"
}

output "dpu_system_id" {
  value       = maas_machine.dpu.id
  description = "MAAS system ID of the DPU"
}
```

The plan declares four resources:

| Resource | Purpose |
|:---|:---|
| `maas_machine.host` | Enlists and commissions the host machine |
| `maas_instance.host_deployment` | Deploys Ubuntu on the host |
| `maas_machine.dpu` | Enlists and commissions the DPU (after host deployment) |
| `maas_instance.dpu_deployment` | Deploys Ubuntu on the DPU, then power-cycles the host |

All machine-specific values are variables, so the plan works for any host-DPU pair without editing the file.

## Gather the required information

Before running the plan, collect the following for both machines:

| Value | Where to find it |
|:---|:---|
| MAAS API URL | MAAS UI address, e.g. `http://<host>:5240/MAAS` |
| MAAS API key | MAAS UI > *Your profile* > *Details* > *API key* |
| PXE MAC address | Label on the NIC, or from the BMC's network summary |
| BMC IP address | Your network inventory or BMC management interface |
| BMC username/password | Your hardware credentials |

## Deploy the host-DPU pair

### 1. Initialize Terraform

Create a directory for your plan, save the `main.tf` content from above into it, then initialize:

```nohighlight
mkdir dpu-host-pair && cd dpu-host-pair
# save main.tf here
terraform init
```

### 2. Set variables

Create a `terraform.tfvars` file with the non-sensitive values:

```hcl
maas_api_url = "http://<MAAS>:5240/MAAS"

host_hostname      = "host-0"
host_pxe_mac       = "<HOST MAC>"
host_power_address = "<HOST BMC IP>"
host_power_user    = "<HOST BMC user>"

dpu_hostname      = "dpu-0"
dpu_pxe_mac       = "<DPU MAC>"
dpu_power_address = "<DPU BMC IP>"
dpu_power_user    = "<DPU BMC user>"

distro_series = "noble"
```

Export the sensitive credentials as environment variables. To avoid them being saved to your shell history, include a leading space before each command:

```nohighlight
 export TF_VAR_maas_api_key="<MAAS API key>"
 export TF_VAR_host_power_pass="<HOST BMC password>"
 export TF_VAR_dpu_power_pass="<DPU BMC password>"
```

### 3. Preview the changes

Run `plan` to see what Terraform will create before committing. Terraform reads `terraform.tfvars` and the `TF_VAR_` environment variables automatically:

```nohighlight
terraform plan
```

Review the output. Terraform will list four resources to be created.

### 4. Apply

When satisfied, apply the plan:

```nohighlight
terraform apply
```

Terraform will prompt for confirmation; type `yes` and press Enter.

### What happens during apply

Terraform works through the four resources in dependency order:

1. **Host commissioning**: MAAS enrolls the host and runs commissioning scripts. This typically takes a few minutes.
2. **Host deployment**: MAAS installs Ubuntu on the host. Once complete, the host is running and the DPU is reachable.
3. **DPU commissioning**: MAAS enrolls the DPU and runs commissioning scripts.  
4. **DPU deployment**: MAAS installs Ubuntu on the DPU. After deployment, a local-exec step power-cycles the host to complete DPU initialization.

You can follow progress in the terminal output:

```nohighlight
maas_machine.host: Creating...
maas_machine.host: Still creating... [10m00s elapsed]
maas_machine.host: Creation complete after 12m30s [id=abc123]
maas_instance.host_deployment: Creating...
...
maas_instance.dpu_deployment: Creation complete after 8m10s [id=xyz789]

Apply complete! Resources: 4 added, 0 changed, 0 destroyed.
```

Total provisioning time is typically 25–40 minutes, depending on your hardware and network speed.

### Verify the deployment

Once `terraform apply` completes:

1. Open the MAAS UI and go to *Hardware* > *Machines*.
2. Confirm that both `host-0` (or your custom hostname) and `dpu-0` appear with status **Deployed**.
3. To inspect commissioning and deployment logs for either machine, click on its name and open the **Logs** tab.

## Optional variables

The plan exposes additional variables with sensible defaults:

| Variable | Default | Description |
|:---|:---|:---|
| `host_hostname` | `host-0` | Hostname assigned to the host machine in MAAS |
| `dpu_hostname` | `dpu-0` | Hostname assigned to the DPU in MAAS |
| `distro_series` | `noble` | Ubuntu release deployed on both machines |
| `maas_snap_channel` | `3.7/stable` | Snap channel used by the power-cycle post-provisioner |

Override any of these in `terraform.tfvars`, for example:

```hcl
host_hostname = "blade-01"
dpu_hostname  = "dpu-blade-01"
distro_series = "jammy"
```
