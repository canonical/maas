This guide explains how we measure MAAS performance, details recent improvements, and explains how to track your own metrics.

## Our reference case

We've improved MAAS API performance through rigorous testing, using scenarios that include five rack controllers, 48 machines per fabric, five VMs per LXD host, and machines with diverse features. Our testing setup is designed to reflect a range of real-world conditions.

We use continuous performance monitoring to track this variety. 

![Performance Monitoring Snapshot](https://discourse-maas-io-uploads.s3.us-east-1.amazonaws.com/original/2X/d/d8a0887dd9d6f01311966c10f5d9093feb76806f.png)

Our daily simulations of 10, 100, and 1000 machines provide detailed insights into scalability. The Jenkins tool tests both the REST and WebSocket APIs, with results stored in a database for analysis through our dashboard.

![Dashboard](https://discourse-maas-io-uploads.s3.us-east-1.amazonaws.com/original/2X/f/f5f831164e70273e81b4120b442469f665e16b47.png)

Comparative testing of stable and development releases helps us identify and fix bugs early. For example, MAAS 3.2 machine listings load 32% faster than in MAAS 3.1 in our tests.

## Work done so far

Our commitment to performance optimisation is ongoing. Some highlights include:

- A [video overview](https://discourse.maas.io/t/maas-show-and-tell-is-maas-fast-yet/6105) of recent enhancements.
- Efforts by our [UI team](https://discourse.maas.io/t/maas-ui-improving-the-performance-of-maas-ui/5820) to improve the user interface.

These examples represent just a part of our comprehensive performance improvement efforts.

## Help us with metrics

Contribute by [tracking your MAAS metrics](https://maas.io/docs/how-to-monitor-maas) and sharing them with us. Your input on machine counts, network sizes, and performance experiences is valuable. Join the discussion on our [Discourse performance forum](https://discourse.maas.io/c/maas-performance/26).

## Recent + upcoming

The MAAS 3.2 update has achieved a 32% speed increase in machine listing through the REST API. We're continuing to work on further enhancements.

## What's next

Our focus now is on optimising other MAAS features, including search functionalities. Feedback and insights are always welcome.
