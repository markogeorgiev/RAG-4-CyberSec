A strong password policy balances security with usability. Here are the core elements:

**Length and complexity**
- Require a minimum of 12–16 characters (length matters more than complexity)
- Encourage passphrases (e.g., "correct-horse-battery-staple") over short complex strings
- Don't over-mandate character types; forcing symbols often leads to predictable patterns like "Password1!"

**Modern best practices (per NIST guidelines)**
- Avoid forced periodic resets unless there's evidence of compromise; frequent rotation leads to weaker, incremental passwords
- Screen new passwords against lists of breached/common passwords
- Allow the full character set, including spaces and Unicode
- Allow long passwords (at least 64 characters max)
- Don't use password hints or knowledge-based security questions

**Protection mechanisms**
- Enforce multi-factor authentication (MFA) — this matters more than password rules alone
- Rate-limit login attempts and add lockout/throttling after failures
- Store passwords hashed with a strong algorithm (bcrypt, scrypt, or Argon2), never plaintext
- Use salting to defend against rainbow table attacks

**Operational policies**
- Ban password reuse across accounts
- Provide a company password manager so users don't resort to sticky notes
- Educate users on phishing, since strong passwords don't help if they're handed over

**What to avoid**
- Composition rules that frustrate users into predictable workarounds
- Storing or transmitting passwords insecurely
- SMS as the only second factor (vulnerable to SIM swapping; prefer authenticator apps or hardware keys)

If this is for client sites you're hosting, the practical priorities are: enforce MFA, hash with Argon2/bcrypt, check against breach lists (e.g., Have I Been Pwned's API), and rate-limit auth endpoints. Want a sample implementation for your FastAPI stack?