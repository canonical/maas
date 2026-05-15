Feature: Device listing

Background:
    Given the user is logged in
    And the user navigates to the devices page

Scenario: The correct heading is rendered
    Then the section header title should be "Devices"

 Scenario: The user can add a tag to a device
    Given the user adds a new device
    When the user opens the device configuration
    And the user adds a tag to the device
    Then the tag should be visible in the device summary