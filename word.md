Why This Backend App Registration Is Needed
Backend API Protection: The backend must have its own app registration so it can be treated as a protected API instead of just a public URL.
Token Validation: The frontend sends an access token whenever it calls the backend. The backend app registration allows the backend to validate that token properly and confirm the request is coming from an authenticated user.
Correct Audience Mapping: The token must be specifically meant for the backend API. Without a backend app registration, the backend cannot properly verify that the token was issued for this API.
User Isolation: The backend needs a real user identity from the token so actions like chat, new chat, delete chat, and conversation history are tied to the correct user and not to a shared fallback identity.
Secure Frontend-to-Backend Communication: The frontend app registration is used for sign-in. The backend app registration is used so the frontend can request permission to call the backend securely.
Principle of Least Privilege: Only approved users and approved frontend calls should be able to access protected backend functionality.
Step 1: Create the App Registration
Go to Entra ID → App registrations → + New registration
Configure:
Name: PSEG Tech Manual Agent - Backend API
Supported account types: Accounts in this organizational directory only
(Single tenant)
Redirect URI: Leave blank
Click Register
Record the following:
Application (client) ID
Directory (tenant) ID
Citations:
Step 2: Expose the Backend API
Open the newly created backend app registration
Go to Expose an API
Under Application ID URI, click Set
Configure the Application ID URI as:
api://<backend-client-id>
Click Save
Citations:
Step 3: Add a Scope for the Backend API
Under Expose an API, click + Add a scope
Configure:
Scope name: access_as_user
Who can consent: Admins and users
Admin consent display name: Access backend API as user
Admin consent description: Allows the application to access the backend API on behalf of the signed-in user
User consent display name: Access backend API as user
User consent description: Allows this app to call the backend API on your behalf
State: Enabled
Click Add scope
Record the full scope value:
api://<backend-client-id>/access_as_user
Citations:
Step 4: Authorize the Frontend to Call the Backend API
Go to the frontend app registration
Open API permissions
Click + Add a permission
Select My APIs
Select the backend API app registration
Choose Delegated permissions
Select:
access_as_user
Click Add permissions
Grant admin consent if required
Citations:
Step 5: Optionally Pre-Authorize the Frontend Application
Go back to the backend app registration
Open Expose an API
Under Authorized client applications, click Add a client application
Enter the frontend Application (client) ID
Select the scope:
api://<backend-client-id>/access_as_user
Save the changes
Citations:
Step 6: Token Configuration for Backend Identity
Open the backend app registration
Go to Token configuration
Add optional claims only if needed
Main user identity should come from the access token claims used by the backend after validation
The backend should use the stable user identifier from the validated token for user-specific operations
Citations:
Step 7: Restrict Backend Access to Approved Users or Groups
Go to Enterprise applications
Open the backend enterprise application
Go to Properties
Set Assignment required? = Yes
Go to Users and groups
Click Add user/group
Assign the required security group
Citations:
Step 8: Frontend Configuration Update
Update the frontend configuration to request the backend API scope
Configure the scope value as:
api://<backend-client-id>/access_as_user
Make sure the frontend sends the access token whenever it calls backend endpoints such as:
chat
stream
new chat
delete chat
conversation history
feedback actions
Citations:
Step 9: Backend Validation Requirements
The backend must validate the bearer access token for every protected API request
The backend should verify:
token is present
token is valid
token is not expired
token belongs to the correct tenant
token audience matches the backend API
user identity can be extracted correctly
After successful validation, the backend should use that user identity for:
chat processing
conversation ownership
new chat creation
delete chat authorization
history retrieval
feedback tracking
If token validation fails, the backend should reject the request
Citations:
Step 10: Production Behavior
Protected backend APIs should not allow anonymous fallback access
Requests without valid tokens should be rejected
Shared or default user identity should not be used in production
All user-specific backend actions must use the validated identity from the access token
Citations:
Summary
Frontend app registration handles user sign-in
Backend app registration handles backend API protection
Frontend requests a token specifically for the backend API
Backend validates that token before running protected actions
This helps secure backend APIs and keep user data isolated correctly
Citations:
