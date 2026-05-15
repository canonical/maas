Feature: Navigation - admin

  Background:
    Given the user is logged in
    And the viewport is "macbook-13"
    And the user navigates to the home page
    And the user clicks the button matching "expand main navigation"
    And the page is loaded

  Scenario: Clicking the logo navigates to Machines
    When the user clicks the "Homepage" link in the main navigation
    Then the pathname should equal "/machines"

  Scenario: Navigating to user preferences via the username link
    When the user clicks the username link in the main navigation
    Then the pathname should equal "/account/prefs/details"
    And the username navigation item should be selected
    And the username link should have current page state

  Scenario Outline: Navigating via the main navigation highlights the active link
    When the user clicks the "<label>" link in the main navigation
    Then the pathname should equal "<path>"
    And the "<label>" navigation item should be selected
    And the "<label>" link should have current page state

    Examples:
      | label       | path                            |
      | Machines    | /machines                       |
      | Devices     | /devices                        |
      | Controllers | /controllers                    |
      | LXD         | /kvm/lxd                        |
      | Images      | /images                         |
      | DNS         | /domains                        |
      | Networks    | /networks/subnets               |
      | Settings    | /settings/configuration/general |
      | AZs         | /zones                          |
