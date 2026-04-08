I need you to inspect my current local codebase and give me a very focused auth/debug summary.

Context:

* Frontend is deployed and can connect to backend.
* Backend health is OK.
* When I click New Chat, it fails.
* Backend Azure logs show: JWT validation failed: Signature verification failed.
* I need to identify exactly where JWT validation is implemented in my local code and whether it matches GCC High / Azure Government token validation.

Please inspect the entire current workspace and give me a clean report with these sections.

1. JWT validation entry points

* Find every file and function that handles:

  * Authorization header
  * Bearer token
  * JWT decode
  * jwks
  * openid configuration
  * issuer
  * audience
  * tenant
  * signature verification
  * PyJWT
  * jose
  * PyJWKClient
  * msal token validation
* For each match, give:

  * file path
  * function name
  * short explanation of what it is doing

2. Actual request path for creating a conversation

* Trace the flow for “New Chat” or conversation creation from frontend to backend.
* Show:

  * frontend file that makes the request
  * request URL/path
  * whether Authorization bearer token is attached
  * backend route file and function that receives it
  * identity/auth code used before conversation is created

3. JWT validation config values

* Find where these variables are read and used:

  * ENTRA_TENANT_ID
  * JWT_AUDIENCE
  * ENTRA_CLOUD
  * NEXT_PUBLIC_API_SCOPE
  * NEXT_PUBLIC_AUTHORITY
  * NEXT_PUBLIC_CLIENT_ID
* For each one, show:

  * file path
  * exact function or class using it
  * what it affects

4. GCC High / Azure Government compatibility

* Check whether token validation uses:

  * microsoftonline.us
  * Azure Government OpenID config
  * Azure Government JWKS endpoint
* Also check whether any code still incorrectly uses:

  * microsoftonline.com
  * public cloud issuer/jwks
* Clearly say whether there is any mismatch.

5. Exact failure point candidates

* Based on the current code, identify the top likely reasons for:

  * “JWT validation failed: Signature verification failed”
* Point to the exact file and line range if possible.

6. Final summary
   Give me:

* the most important auth-related files to screenshot for review
* the one or two most suspicious code blocks
* whether the code is mixed between EasyAuth header-based identity and real JWT validation

Important:

* Do not give me a huge generic explanation.
* Keep it structured.
* Show file paths clearly.
* Quote only small relevant snippets.
* Prefer bullet points with exact filenames and functions.
