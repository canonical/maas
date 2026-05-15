Feature: Settings page headings

  Scenario Outline: Settings subpage displays the correct heading
    Given the user is logged in
    When the user navigates to the <page> page
    Then the "<label>" heading should exist

     Examples:
      | page                            | label                 |
      | settings general                | General               |
      | settings commissioning          | Commissioning         |
      | settings deploy                 | Deploy                |
      | settings kernel parameters      | Kernel parameters     |
      | settings security protocols     | Security protocols    |
      | settings secret storage         | Secret storage        |
      | settings token expiration       | Token expiration      |
      | settings ipmi settings          | IPMI settings         |
      | settings users                  | Users                 |
      | settings single sign-on         | OIDC/Single sign-on   |
      | settings ubuntu images          | Ubuntu                |
      | settings windows images         | Windows               |
      | settings vmware images          | VMware                |
      | settings license keys           | License keys          |
      | settings storage                | Storage               |
      | settings proxy                  | Proxy                 |
      | settings dns                    | DNS                   |
      | settings ntp                    | NTP                   |
      | settings syslog                 | Syslog                |
      | settings network discovery      | Network discovery     |
      | settings commissioning scripts  | Commissioning scripts |
      | settings deployment scripts     | Deployment scripts    |
      | settings testing scripts        | Testing scripts       |
      | settings dhcp snippets          | DHCP snippets         |
      | settings package repositories   | Package repositories  |