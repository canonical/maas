Feature: KVM listing

  Scenario: The correct heading is rendered
    Given the user is logged in
    When the user navigates to the kvm page
    Then the main toolbar heading should be "LXD"