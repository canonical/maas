@kernel-parameters-cleanup
Feature: Settings kernel parameters

  Background:
    Given the user is logged in
    And the user navigates to the settings kernel parameters page

  Scenario: The user can update kernel parameters
    When the user clears the kernel parameters field
    And the user enters the new kernel parameters
    And the user saves the kernel parameters
    Then the save button should be disabled
    And the kernel parameters field should have the updated value
    When the user refreshes the page
    Then the kernel parameters field should have the updated value