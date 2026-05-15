## MAAS UI

[![CI](https://github.com/canonical/maas-ui/actions/workflows/test.yml/badge.svg?branch=main)](https://github.com/canonical/maas-ui/actions/workflows/test.yml?query=branch%3Amain)
[![Accessibility](https://github.com/canonical/maas-ui/actions/workflows/accessibility.yml/badge.svg?branch=main)](https://github.com/canonical/maas-ui/actions/workflows/accessibility.yml?query=branch%3Amain)
[![Cypress](https://github.com/canonical/maas-ui/actions/workflows/cypress.yml/badge.svg?branch=main)](https://github.com/canonical/maas-ui/actions/workflows/cypress.yml?query=branch%3Amain)
[![sitespeed.io](https://github.com/canonical/maas-ui/actions/workflows/sitespeed.yml/badge.svg?branch=main)](https://github.com/canonical/maas-ui/actions/workflows/sitespeed.yml?query=branch%3Amain)
[![MAAS Docs link checker](https://github.com/canonical/maas-ui/actions/workflows/links-checker.yml/badge.svg?branch=main)](https://github.com/canonical/maas-ui/actions/workflows/links-checker.yml?query=branch%3Amain)
[![Commitizen friendly](https://img.shields.io/badge/commitizen-friendly-brightgreen.svg)](http://commitizen.github.io/cz-cli/)
[![Code Coverage](https://img.shields.io/badge/code--coverage-report-brightgreen.svg)](https://canonical.github.io/maas-ui/)
[![Build upload](https://github.com/canonical/maas-ui/actions/workflows/upload.yml/badge.svg)](https://github.com/canonical/maas-ui/actions/workflows/upload.yml?query=branch%3Amain)

- [MAAS UI](#maas-ui)
- [About](#about)
- [MAAS UI Overview](#maas-ui-overview)
- [Contributing](#contributing)
- [Feedback](#feedback)
- [Integration testing](#integration-testing)
- [Release Process](#release-process)
- [Related Projects](#related-projects)
  - [MAAS](#maas)
  - [LXD](#lxd)
- [Built With](#built-with)
- [Team Members](#team-members)
- [Code of Conduct](#code-of-conduct)
- [License](#license)

## About

MAAS is an open-source tool that lets you build a data centre from bare-metal servers. You can discover, commission, deploy, and dynamically reconfigure a large network of individual units.

![screenshot of MAAS UI displaying 1000 machines](https://user-images.githubusercontent.com/7452681/234197707-a25b2231-1ca4-4d80-9e42-53d99c4e2cf1.png)

This repository contains the sourcecode for the [MAAS](https://maas.io) web app, maas-ui.

## MAAS UI Overview

[MAAS UI Overview](docs/MAASUI.md)

## Contributing

Community contributions are most welcome, and there are a number of ways to participate:

- [Submit bugs and feature requests](https://maas.io/docs/how-to-review-and-report-bugs)
- [Assist with code review](https://github.com/canonical/maas-ui/pulls)
- [Submit bugs for the MAAS website](https://github.com/canonical/maas.io)
- [Contribute to MAAS documentation](https://maas.io/docs/how-to-contribute-to-maas-documentation)

When submitting a PR, please take note that MAAS UI uses the [conventional commit](https://www.conventionalcommits.org/en/v1.0.0/) format. To help you conform to this, you can run `yarn commit` instead of `git commit` for an interactive prompt.

Please see [HACKING](/docs/HACKING.md) for details on setting up a MAAS UI development environment.

## Feedback

- Ask a question about MAAS on [Discourse](https://discourse.maas.io/).
- File a [MAAS issue](https://bugs.launchpad.net/maas/+filebug).
  - If you think that the issue is related to the UI, please add a `ui` tag

## Integration testing

[Integration testing](docs/INTEGRATION.md)

## Release Process

[Release Process](docs/RELEASE.md)

## Related Projects

### MAAS

MAAS server source and issue tracking [can be found on Launchpad](https://launchpad.net/maas).

### LXD

[LXD](https://github.com/lxc/lxd) is a next generation system container and virtual machine manager, used extensively by MAAS.

## Built With

- [React](https://reactjs.org/)
- [Redux](https://redux.js.org/)
- [TypeScript](https://www.typescriptlang.org/)

## Team Members

[MAAS Tribe](https://discourse.canonical.com/t/maas-tribe/272) and [Canonical Web & Design](https://github.com/orgs/canonical/teams/web-and-design/members)

## Code of Conduct

This project adopts the [Ubuntu Code of Conduct](https://ubuntu.com/community/code-of-conduct).

## License

Code licensed AGPLv3 by Canonical Ltd.

With ♥ from Canonical
