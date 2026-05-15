Feature: DNS record assignment

  Background:
    Given the user is logged in

  Scenario: Create DNS record from a device IP and follow link to device details
    Given the user navigates to the subnets page
    When the user creates a subnet with a known CIDR
    And the user navigates to the devices page
    And the user clicks the "Add device" button
    And the user enters valid device details
    And the user clicks the "Save device" button
    And the user navigates to the domains page
    And the DNS default domain row is opened
    And the user clicks the "Add record" button
    And the user enters a record name
    And the user enters the same IP address in the "data" field
    And the user submits the form
    Then the record name should appear as a link in the DNS record list
    When the created DNS record link is opened
    Then the pathname should equal "/device/*"
