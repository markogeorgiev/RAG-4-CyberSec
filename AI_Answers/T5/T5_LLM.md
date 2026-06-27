Verifying software update legitimacy comes down to confirming two things: the update actually came from the vendor (authenticity) and wasn't tampered with in transit (integrity).

**Cryptographic signatures.** This is the strongest method. Vendors sign releases with a private key; you verify with their public key.

- GPG/PGP: `gpg --verify file.sig file` after importing the vendor's published key. Confirm the key fingerprint matches one obtained from an independent channel, not just the download page.
- Code signing: On Windows, check the Authenticode signature (right-click → Properties → Digital Signatures, or `signtool verify`). On macOS, use `codesign --verify --deep --strict` and `spctl --assess`.

**Checksums (hashes).** Compare the published hash against what you compute locally:
- `sha256sum file` (Linux), `shasum -a 256 file` (macOS), `Get-FileHash file` (PowerShell).
- A matching hash only proves integrity if the hash itself came from a trusted source. If an attacker controls the download page, they can swap both file and hash—so signatures are stronger.

**Transport and source.**
- Download over HTTPS from the official domain; check the TLS certificate is valid and the domain is correct (watch for typosquatting).
- Prefer official package managers (apt, dnf, Homebrew, winget) and app stores, which verify signatures automatically.

**Built-in auto-update mechanisms.** Most modern software verifies signatures internally before installing. Keep auto-update enabled where you trust the vendor, and only disable it for deliberate manual control.

**Practical checks:**
- Get the public key/fingerprint from a separate channel than the download (e.g., a keyserver, the vendor's GitHub, documentation) so a compromised page can't feed you a fake key.
- Be wary of update prompts from pop-ups, emails, or third-party sites—initiate updates yourself through the app or official site.

The hierarchy: signature verification with an independently trusted key > checksum from a trusted source > HTTPS from official domain. Use the strongest available.