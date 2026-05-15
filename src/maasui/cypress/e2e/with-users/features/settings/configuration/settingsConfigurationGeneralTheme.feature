Feature: Settings general theme

  Background:
    Given the user is logged in
    And the user navigates to the settings general page
    And the default theme is applied
    When the user selects the "Red" theme

  Scenario: The selected theme is previewed live
    Then the main navigation should use the "is-maas-red" theme class

  Scenario: The selected theme persists after saving and refreshing the page
    And the user clicks the "Save" button
    Then the "Save" button should be disabled
    When the user refreshes the page
    Then the main navigation should use the "is-maas-red" theme class

  Scenario: The selected theme persists after saving and navigating away from page
    And the user clicks the "Save" button
    Then the "Save" button should be disabled
    When the user clicks the "Deploy" link
    Then the main navigation should use the "is-maas-red" theme class

  Scenario: The selected theme is reverted if it is not saved and the page is refreshed
    And the user refreshes the page
    Then the main navigation should use the "is-maas-default" theme class

  Scenario: The selected theme is reverted when the user clicks cancel
    And the user clicks the "Cancel" button
    Then the main navigation should use the "is-maas-default" theme class

  Scenario: The selected theme is reverted when the user navigates away to another page without saving
    And the user clicks the "Deploy" link
    Then the main navigation should use the "is-maas-default" theme class