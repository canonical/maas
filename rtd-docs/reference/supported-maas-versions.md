# Supported MAAS versions

The four most recent MAAS versions are supported. When a new version of MAAS is released, the oldest version goes out of support. The release cadence for MAAS is every 6 months (tentatively), aiming to release around the same time as Ubuntu. There are currently no LTS versions of MAAS.

The table below lists dependencies for each MAAS release, including the base Ubuntu LTS version. This is most relevant for the deb packages, which can be installed only on the corresponding Ubuntu version. Snap version of MAAS can run on other Ubuntu versions, because it is built with a base image that corresponds to the Ubuntu LTS version listed in the table, e.g. MAAS 3.6 snap is based on core24 snap. MAAS aims to move to the new Ubuntu LTS six months after its release.

| Supported MAAS Versions | Dependencies  | Release Date | Type of Support |
| - | - | - | - |
| 3.7 | Ubuntu 24.04</br>PostgreSQL 16 |  December 2025  | Fully Supported |
| 3.6 | Ubuntu 24.04</br>PostgreSQL 14 (16 recommended) |  April 2025  | Fully Supported |
| 3.5 | Ubuntu 22.04</br>PostgreSQL 14 |  July 2024  | Bugfix only, no features, no backports |
| 3.4 | Ubuntu 22.04</br>PostgreSQL 14 |  January 2024  | Bugfix only, no features, no backports |
| 3.3 | Ubuntu 22.04</br>PostgreSQL 12 (14 recommended) |  February 2023  | Unsupported |
| 3.2 | Ubuntu 20.04</br>PostgreSQL 12 |  June 2022  | Unsupported |
| 3.1 | Ubuntu 20.04</br>PostgreSQL 12 |  October 2021  | Unsupported |
| 3.0 | Ubuntu 20.04</br>PostgreSQL 12 |  April 2021  | Unsupported |
| 2.9 | Ubuntu 20.04</br>PostgreSQL 10 (12 recommended) |  October 2020  | Unsupported |
| 2.8 | Ubuntu 18.04</br>PostgreSQL 10 |  April 2020  | Unsupported |
