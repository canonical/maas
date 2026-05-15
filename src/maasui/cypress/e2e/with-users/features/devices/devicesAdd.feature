Feature: Device add

  Background:
    Given the user is logged in
    And the user navigates to the devices page

  Scenario: The user can add a new device
    When the user clicks the "Add device" button
    And the user enters valid device details
    And the user clicks the "Save device" button
    Then the new device should appear in the device list
