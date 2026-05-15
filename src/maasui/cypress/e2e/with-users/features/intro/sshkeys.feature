Feature: SSH keys - new user intro

  Scenario: A new user sees the SSH keys import prompt on first login
    Given the user is logged in
    When the admin creates a new user account
    And the admin logs out
    And the new user logs in with their credentials
    Then the pathname should equal "/intro/user"
    And the SSH keys import prompt should be visible
