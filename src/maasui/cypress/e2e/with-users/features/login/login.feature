Feature: Login page

Background:
    Given the user navigates to the home page

Scenario: An error message is displayed if invalid login credentials are submitted
    When the user enters invalid username and password
    Then the alert "Please enter a correct username and password" should be visible

Scenario: The user is logged in and redirected to the intro page if valid username and password are provided
    Given the skipsetupintro cookie is set to "false"
    When the user provides correct username and password
    Then the pathname should equal "/intro"

Scenario: The user is logged in and redirected to user setup page if the setup intro is skipped
    Given the skipsetupintro cookie is set to "true"
    Given the skipintro cookie is set to "false"
    When the user provides correct username and password
    Then the pathname should equal "/intro/user"

Scenario: The user is logged in and redirected to the machine list page if setup and user intros are skipped
    Given the skipsetupintro cookie is set to "true"
    Given the skipintro cookie is set to "true"
    When the user provides correct username and password
    Then the pathname should equal "/machines"

Scenario: The user is logged in via SSO and redirected to the machine list page if setup and user intros are skipped
    Given the skipsetupintro cookie is set to "true"
    Given the skipintro cookie is set to "true"
    When the user clicks on the "Login with keycloak" button
    Then the pathname should equal "/machines"