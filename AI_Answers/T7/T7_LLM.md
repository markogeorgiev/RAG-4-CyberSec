If you're dealing with an active ransomware attack right now, here's the immediate sequence:

**Contain first.** Disconnect affected machines from the network (unplug ethernet, disable Wi-Fi), but don't power them off—memory may hold forensic evidence and sometimes decryption keys. Isolate, don't shut down.

**Don't pay yet (and ideally not at all).** Payment doesn't guarantee recovery, marks you as a target for repeat attacks, and may be legally restricted depending on the attacker. Treat it as a last resort after exhausting other options.

**Identify the scope.** Determine which systems are encrypted, what strain you're hit with (sites like ID Ransomware or No More Ransom can sometimes identify it from a ransom note or encrypted file), and whether data was exfiltrated—modern ransomware usually steals data before encrypting and threatens to leak it.

**Preserve evidence.** Keep the ransom note, sample encrypted files, and logs. You'll need them for forensics, insurance, and law enforcement.

**Notify the right people.** Internal incident response/IT, your cyber-insurance carrier (often before doing much else—they may dictate the process and provide a response firm), legal counsel, and law enforcement. In the US that's the FBI/IC3 and CISA; in the EU your national CERT and data protection authority. There may be mandatory breach-notification deadlines (e.g. GDPR's 72 hours) if personal data was exposed.

**Recover from clean backups.** Restore from backups verified to be uninfected, after confirming the attacker no longer has access. Rebuild compromised systems rather than trusting them.

**Find the entry point.** Identify how they got in (phishing, exposed RDP, unpatched VPN, stolen credentials) and close it before reconnecting, or you'll be re-encrypted.

**After the fire's out:** rotate all credentials, patch, enforce MFA, segment your network, and move to offline/immutable backups.

Two things would help me give you more specific guidance: is this an active attack happening now, or are you planning ahead? And roughly what scale—a single machine, a small business network, or a larger organization?

Given your client-hosting setup, the prevention side (immutable backups, network segmentation between client sites, locked-down SSH/deployment access) is worth a separate deeper look once the immediate situation is clear.