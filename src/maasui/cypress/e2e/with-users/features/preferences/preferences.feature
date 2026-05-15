Feature: User preferences

  Scenario: The correct heading is rendered
    Given the user is logged in
    When the user navigates to the preferences page
    Then the side navigation title should be "My preferences"