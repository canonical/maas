> *Errors or typos? Topics missing? Hard to read? <a href="https://docs.google.com/forms/d/e/1FAIpQLScIt3ffetkaKW3gDv6FDk7CfUTNYP_HGmqQotSTtj2htKkVBw/viewform?usp=pp_url&entry.1739714854=https://maas.io/docs/delving-into-maas-logging-practices" target = "_blank">Let us know.</a>*
	
Understanding the different types of logs in MAAS is essential for maintaining and troubleshooting your environment. Each type of log serves a specific purpose, helping you monitor system activities, track user actions, and ensure that hardware is set up correctly. By knowing what each log type does and how to access it, you can quickly identify issues, improve system performance, and maintain security. Here’s a detailed look at the main types of logs available in MAAS.

## Types of logs

**Event logs** track system activities to help fix problems. For example, if a machine fails to deploy properly, event logs can show exactly where the deployment process went wrong. You might see a log entry indicating a failure to communicate with a specific service, which can help you pinpoint the issue and fix it quickly.

**Audit logs** record user actions for security and accountability. For instance, if a critical configuration change was made and caused issues, audit logs can show which user made the change, when it happened, and what exactly was modified. This helps ensure accountability and can prevent unauthorized actions by quickly identifying who is responsible for specific activities.

**Commissioning logs** track the hardware setup process. Commissioning is the process of preparing and configuring new hardware so it can be used in your environment. This involves running tests, gathering hardware details, and ensuring the machine is ready for deployment.

**Testing logs** capture the results of hardware tests. For example, a test might check the health of a machine's hard drive using smartctl to look for signs of failure, such as bad sectors or read errors. Logging these test results helps you catch potential hardware issues early, making it easier to replace faulty parts before they cause downtime.

