Understanding the machine life-cycle is key to leveraging MAAS effectively. Machines under MAAS control transition through specific states, primarily user-controlled, except for the "failed" state, which MAAS assigns when certain operations can't be completed successfully.

## Machine states

The standard life-cycle includes the following states:

- **New:** Machines configured to network boot on a MAAS-accessible subnet are automatically enlisted with a "NEW" status.

- **Commissioning:** Selected "NEW" machines undergo commissioning, where MAAS boots them via PXE, loads an ephemeral Ubuntu OS into RAM, and assesses hardware configurations. Failures during this process result in a "FAILED" state.

- **Testing:** Post-commissioning, MAAS performs basic hardware tests. Machines that don't pass these tests are moved to a "FAILED" state.

- **Ready:** Machines that pass testing are marked "READY," indicating they're prepared for deployment.

- **Allocated:** Users allocate "READY" machines to take ownership, preventing others from deploying them.

- **Deploying:** Allocated machines are deployed with the specified OS and configurations.

- **Deployed:** Machines successfully deployed and operational.

- **Releasing:** Deployed machines can be released back to the pool, optionally undergoing disk erasure.

## Exceptional states

- **Rescue mode:** Allows troubleshooting of deployed or broken machines by booting into an ephemeral environment.

- **Broken:** Machines with critical issues can be marked as "BROKEN," indicating they require attention before returning to the pool.

Understanding these states and transitions is crucial for effective machine management in MAAS.

## Enlistment and commissioning

MAAS simplifies machine management through enlistment and commissioning processes:

- **Enlistment:** MAAS discovers machines configured to netboot on accessible subnets, boots them into an ephemeral Ubuntu environment, and gathers basic hardware information, assigning them a "NEW" status.

- **Commissioning:** Administrators select "NEW" machines for commissioning, during which MAAS collects detailed hardware information and performs initial configurations. Successful commissioning transitions machines to the "READY" state.

Administrators can also manually add machines to MAAS, which automatically commissions them.

## Cloning configurations (MAAS 3.1+)

MAAS 3.1 introduced the ability to clone configurations from one machine to others, streamlining the setup of multiple machines with similar settings. This feature allows users to replicate network and storage configurations, provided certain conditions are met, such as matching interface names and adequate storage capacity on destination machines.

## Adding live machines (MAAS 3.1+)

MAAS 3.1 also allows the addition of machines already running workloads without disrupting them. Administrators can specify that a machine is already deployed, preventing the standard commissioning process and marking it as deployed. A provided script can collect hardware information from these machines and send it back to MAAS.

By understanding and utilizing these processes and features, administrators can effectively manage machines within MAAS, ensuring efficient deployment and maintenance across their infrastructure.
