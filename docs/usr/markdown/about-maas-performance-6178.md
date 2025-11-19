
Performance directly affects how quickly MAAS can list, commission, and deploy machines.  For large-scale environments, small slowdowns can add up.  This page explains how we measure MAAS performance, what improvements we’ve made so far, and how you can track and share your own results.


## How we measure

To keep MAAS fast, we run continuous performance tests that mimic real-world data center conditions:

- Reference environment:
  - 5 rack controllers
  - 48 machines per fabric
  - 5 VMs per LXD host
  - Machines with varied hardware features

- Test runs: Daily simulations at 10, 100, and 1000 machines.

- APIs tested: Both REST and WebSocket APIs.

- Tooling: Jenkins executes the scenarios, results are stored in a database, and we review them via dashboards.

![Performance Monitoring Snapshot](https://discourse-maas-io-uploads.s3.us-east-1.amazonaws.com/original/2X/d/d8a0887dd9d6f01311966c10f5d9093feb76806f.png)

This lets us see how new changes scale before they reach users.  We also compare development and stable releases to spot regressions early.

Example result: In MAAS 3.2, machine listings through the REST API loaded 32% faster than in 3.1.

![Dashboard](https://discourse-maas-io-uploads.s3.us-east-1.amazonaws.com/original/2X/f/f5f831164e70273e81b4120b442469f665e16b47.png)


## Work done so far

Some recent highlights:

- A [video overview](https://discourse.maas.io/t/maas-show-and-tell-is-maas-fast-yet/6105) that walks through major performance improvements.
- Ongoing work by the [UI team](https://discourse.maas.io/t/maas-ui-improving-the-performance-of-maas-ui/5820) to make the interface faster and smoother.

These efforts are part of a broader program of optimization across the product.


## How you can help

Your metrics and feedback are essential.  Here’s how you can contribute:

- [Track your MAAS metrics](https://canonical.com/maas/docs/how-to-monitor-maas) using Prometheus and Grafana.
- Share results like machine counts, network sizes, and API response times.
- Join the conversation on the [MAAS performance forum](https://discourse.maas.io/c/maas-performance/26).

This input helps us validate improvements against real-world usage.


## What’s next

We’re continuing to target areas that matter most in large environments.  Expect further improvements in:

- Search and filtering performance
- Scalability of commissioning and deployment
- Dashboard responsiveness

Your feedback helps prioritize where we focus next.


## Next steps for you

- Learn [how to monitor MAAS](https://canonical.com/maas/docs/how-to-monitor-maas)
- Peruse the [MAAS metrics reference](https://canonical.com/maas/docs/reference-maas-metrics)
- Join the [performance forum](https://discourse.maas.io/c/maas-performance/26)
