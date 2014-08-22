#!/usr/bin/python

# quick and dirty python mailer, called by VmBackup.py
# configure / uncomment the smtp_server / from_addr lines.

import sys, smtplib
from email.MIMEText import MIMEText

global smtp_server
global from_addr

# configure and uncomment out next two lines
#smtp_server = 'your-mail-server'
#from_addr = 'your-from-address@your-domain'

def send_email(to, subject, body_fname):

    message = open('%s' % body_fname, 'r').read()

    msg = MIMEText(message)
    msg['subject'] = subject
    msg['From'] = from_addr
    msg['To'] = to

    s = smtplib.SMTP(smtp_server)
    s.sendmail(from_addr, to.split(','), msg.as_string())
    s.quit()

if __name__ == '__main__':

    if len(sys.argv) < 4:
        print 'Usage:'
        print sys.argv[0], '<to> <subject> <body-filename>'
        sys.exit(1)

    send_email(sys.argv[1], sys.argv[2], sys.argv[3])

