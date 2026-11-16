# Product Steering

## Product Vision

MAAS (Metal as a Service) lets operators manage physical servers like cloud VMs: discover, provision,
deploy, and tear down bare-metal machines on demand, then hand them to orchestration tools
(Ansible, Chef, Puppet, Salt, Juju).

## Target Users / Personas

- **Infrastructure operators:** manage fleets of bare-metal servers, need discovery/commissioning/deployment at scale.
- **Platform teams:** need to hand provisioned bare metal to higher-level orchestration (Juju, k8s, OpenStack).

## Value Proposition

Cloud-like elasticity (boot, check, redeploy, reclaim) for physical hardware, without manual provisioning per server.

## Product Boundaries

### In Scope

- Hardware discovery, commissioning, deployment, power management, DHCP/DNS/TFTP services for machines.
- Region/rack controller architecture; v3 API migration (FastAPI + service layer) alongside legacy Django.

### Out of Scope

- Workload orchestration itself (left to Juju/Ansible/etc.) — MAAS hands off provisioned nodes.

## Success Metrics

- [Open Question] No metrics captured yet — org-specific; ask if needed later.

## Domain Glossary

- **Region controller:** central Django-based control plane (`maasserver`).
- **Rack controller:** per-network-segment service (`provisioningserver`, boot/power/DHCP).
- **Commissioning:** hardware discovery/test phase before deployment.
- **v3 API:** new FastAPI-based REST API (`maasapiserver` + `maasservicelayer`), replacing legacy Django API over time.
