# Passkey sign-in

Existing users can register passkeys under **Profile settings → Security →
Passkeys**, then choose **Sign in with a passkey** on Plane's sign-in screen.
Registration and authentication require device user verification (for example,
a fingerprint, face, device PIN, or security key PIN). Keep another sign-in
method for recovery. Removing a passkey removes that credential from future
sign-ins; it does not sign out existing sessions.

`WEB_URL` must be the canonical HTTPS URL of the web app. Its hostname is the
WebAuthn relying party ID and its origin is checked on every verification.
Changing that hostname requires users to register new passkeys. HTTP localhost
is supported for development. No additional credentials or external identity
provider are needed. Private keys remain with the user's authenticator.

## Session endpoints

Routes are under `/auth/passkeys/`; API keys are not accepted. All write requests,
including anonymous login, require a CSRF token from `/auth/get-csrf-token/` in
the `X-CSRFTOKEN` header and the matching cookie. Registration and sign-in share
the authentication rate limit. Listing and deletion use a separate per-user
budget of 30 requests per minute, so opening settings does not consume sign-in
attempts.

| Method | Route                              | Access                                      |
| ------ | ---------------------------------- | ------------------------------------------- |
| GET    | `/auth/passkeys/`                  | Current user's credential names and dates   |
| DELETE | `/auth/passkeys/{id}/`             | Current user's credential only              |
| POST   | `/auth/passkeys/register/options/` | Authenticated user                          |
| POST   | `/auth/passkeys/register/verify/`  | Authenticated user; `{name, credential}`    |
| POST   | `/auth/passkeys/login/options/`    | Anonymous or authenticated                  |
| POST   | `/auth/passkeys/login/verify/`     | `{credential}`; returns a safe redirect URL |

Challenges expire after five minutes, are bound to the browser session and
ceremony, and are consumed once, including across concurrent requests. A Redis
atomic ADD guards against session snapshot replay. Login verifies the stored
public key, expected origin/RP ID, user handle, user verification flag, and
signature counter. Revoked credentials, inactive accounts, and bot accounts
cannot authenticate. A per-credential database row lock serializes counter
updates. Backed-up/synced authenticators with a zero counter are supported.

Apply migration `0127_passkey` before starting API workers with this feature.
