# Performance

Performance directly affects how quickly MAAS can list, commission, and deploy machines. For large-scale environments, small slowdowns can add up. This page explains how we measure MAAS performance, what improvements we’ve made so far, and how you can track and share your own results.

## How we measure

To keep MAAS fast, we run continuous performance tests that mimic real-world data center conditions:

- Reference environment:
  - 5 rack controllers
  - 48 machines per fabric
  - Machines with varied hardware features

- Test runs: Daily simulations at 10, 100, and 1000 machines.

- APIs tested: Both REST and WebSocket APIs.

- Tooling: Jenkins executes the scenarios, results are stored in a database, and we review them via dashboards.

![Performance Monitoring Snapshot](/images/explanation/performance/performance_monitoring.webp)

This lets us see how new changes scale before they reach users. We also compare development and stable releases to spot regressions early.

Example result: In MAAS 3.2, machine listings through the REST API loaded 32% faster than in 3.1.

![Dashboard](/images/explanation/performance/dashboard.webp)

## Work done so far

Some recent highlights:

- A [video overview](https://discourse.maas.io/t/maas-show-and-tell-is-maas-fast-yet/6105) that walks through major performance improvements.
- Ongoing work by the [UI team](https://discourse.maas.io/t/maas-ui-improving-the-performance-of-maas-ui/5820) to make the interface faster and smoother.

These efforts are part of a broader programme of optimisation across the product.

### Machine listing

The REST machine list keeps its full response structure while loading latest
script results and status events in batches. These caches live on the objects
loaded for each request; they are not shared across requests. Boot-device NUMA
relations and parent machines are loaded with the machine query.

Status selection retains the detail endpoint's rules: script results are selected
across all runs, separately for each machine, script name, disk, and interface.
Aborted and installation results are excluded only after selecting the latest
result. Status events use creation time, then event ID, and include only events
at INFO level or higher.

Default-gateway candidates and explicit-link interfaces are also batch-loaded.
Automatic selection still considers all node configurations; explicit links use
only the current configuration and retain their existing interface ordering.
DHCP resolution selects the newest discovered address across every interface
linked to the DHCP address, including interfaces outside the filtered machine
list. Missing discoveries retain the original DHCP address and subnet.

Effective interface MTUs are computed once per request over the interface graph,
including descendants beyond the old fixed-depth prefetches. Virtual-disk groups
and the subnet/VLAN relations emitted with interface addresses are eager-loaded.
These optimizations do not change live model lookups outside prepared list
responses, and prepared objects must not be reused after configuration changes.

Performance measurements must include Piston JSON rendering, not just the
machine queryset, and use representative network and storage topologies.

## How you can help

Your metrics and feedback are essential. Here’s how you can contribute:

- [Track your MAAS metrics](/how-to-guides/monitor-maas.md) using Prometheus and Grafana.
- Share results like machine counts, network sizes, and API response times.
- Join the conversation on the [MAAS performance forum](https://discourse.maas.io/c/maas-performance/26).

This input helps us validate improvements against real-world usage.

## What’s next

We’re continuing to target areas that matter most in large environments. Expect further improvements in:

- Search and filtering performance
- Scalability of commissioning and deployment
- Dashboard responsiveness

Your feedback helps prioritise where we focus next.

## Next steps for you

- Learn [how to monitor MAAS](/how-to-guides/monitor-maas.md)
- Peruse the [MAAS metrics reference](/reference/configuration-guides/metrics.md)
- Join the [performance forum](https://discourse.maas.io/c/maas-performance/26)
