Feature: Controller listing

  Scenario: The correct heading is rendered
    Given the user is logged in
    When the user navigates to the controllers page
    Then the heading should be "Controllers"
