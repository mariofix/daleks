```bash
2026-03-15T21:55:22.102387-03:00 lin2 postfix/submission/smtpd[2257785]: connect from unknown[172.19.0.1]
2026-03-15T21:55:22.116241-03:00 lin2 postfix/submission/smtpd[2257785]: Anonymous TLS connection established from unknown[172.19.0.1]: TLSv1.3 with cipher TLS_AES_256_GCM_SHA384 (256/256 bits) key-exchange X25519 server-signature RSA-PSS (2048 bits) server-digest SHA256
2026-03-15T21:55:22.162433-03:00 lin2 postfix/submission/smtpd[2257785]: 27937120C92: client=unknown[172.19.0.1], sasl_method=PLAIN, sasl_username=hola@fonotarot.cl
2026-03-15T21:55:22.164603-03:00 lin2 postfix/sender-cleanup/cleanup[2259668]: 27937120C92: replace: header MIME-Version: 1.0 from unknown[172.19.0.1]; from=<hola@fonotarot.cl> to=<mariohernandezc@gmail.com> proto=ESMTP helo=<lin2.156.cl>: MIME-Version: 1.0
2026-03-15T21:55:22.164611-03:00 lin2 postfix/sender-cleanup/cleanup[2259668]: 27937120C92: message-id=<>
2026-03-15T21:55:22.210604-03:00 lin2 postfix/qmgr[2501]: 27937120C92: from=<hola@fonotarot.cl>, size=225, nrcpt=1 (queue active)
2026-03-15T21:55:22.212535-03:00 lin2 postfix/submission/smtpd[2257785]: disconnect from unknown[172.19.0.1] ehlo=2 starttls=1 auth=1 mail=1 rcpt=1 data=1 quit=1 commands=8
2026-03-15T21:55:22.285542-03:00 lin2 postfix/smtpd-amavis/smtpd[2259671]: connect from localhost[127.0.0.1]
2026-03-15T21:55:22.288542-03:00 lin2 postfix/smtpd-amavis/smtpd[2259671]: 46593121095: client=localhost[127.0.0.1]
2026-03-15T21:55:22.291352-03:00 lin2 postfix/cleanup[2259672]: 46593121095: message-id=<DSNfk9FtZ1Sfslc@lin2.156.cl>
2026-03-15T21:55:22.293526-03:00 lin2 postfix/smtpd-amavis/smtpd[2259671]: disconnect from localhost[127.0.0.1] ehlo=1 mail=1 rcpt=1 data=1 quit=1 commands=5
2026-03-15T21:55:22.297235-03:00 lin2 amavis[2243374]: (2243374-09) Blocked BAD-HEADER-0 {BouncedOpenRelay,Quarantined}, [172.19.0.1]:40056 <hola@fonotarot.cl> -> <mariohernandezc@gmail.com>, quarantine: f/badh-fk9FtZ1Sfslc, Queue-ID: 27937120C92, mail_id: fk9FtZ1Sfslc, Hits: -, size: 191, 82 ms
2026-03-15T21:55:22.297412-03:00 lin2 postfix/qmgr[2501]: 46593121095: from=<>, size=2323, nrcpt=1 (queue active)
2026-03-15T21:55:22.305320-03:00 lin2 postfix/smtp-amavis/smtp[2259669]: 27937120C92: to=<mariohernandezc@gmail.com>, relay=127.0.0.1[127.0.0.1]:10024, delay=0.14, delays=0.05/0/0/0.09, dsn=2.5.0, status=sent (250 2.5.0 Ok, id=2243374-09, BOUNCE)
2026-03-15T21:55:22.305484-03:00 lin2 postfix/qmgr[2501]: 27937120C92: removed
2026-03-15T21:55:22.314112-03:00 lin2 dovecot: lmtp(2259838): Connect from local
2026-03-15T21:55:22.331769-03:00 lin2 dovecot: lmtp(hola@fonotarot.cl)<2259838><Y6a3EvpUt2l+eyIAYRBqSw>: sieve: msgid=<DSNfk9FtZ1Sfslc@lin2.156.cl>: stored mail into mailbox 'INBOX'
2026-03-15T21:55:22.333007-03:00 lin2 postfix/lmtp[2259673]: 46593121095: to=<hola@fonotarot.cl>, relay=lin2.156.cl[/var/run/dovecot/lmtp], delay=0.04, delays=0.01/0/0.02/0.02, dsn=2.0.0, status=sent (250 2.0.0 <hola@fonotarot.cl> Y6a3EvpUt2l+eyIAYRBqSw Saved)
2026-03-15T21:55:22.333934-03:00 lin2 postfix/qmgr[2501]: 46593121095: removed
2026-03-15T21:55:22.334842-03:00 lin2 dovecot: lmtp(2259838): Disconnect from local: Logged out (state=READY)
``` 
