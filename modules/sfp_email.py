# -*- coding: utf-8 -*-
# -------------------------------------------------------------------------------
# Name:         sfp_email
# Purpose:      SpiderFoot plug-in for scanning retrieved content by other
#               modules (such as sfp_spider) and identifying e-mail addresses
#
# Author:      Steve Micallef <steve@binarypool.com>
#
# Created:     06/04/2012
# Copyright:   (c) Steve Micallef 2012
# Licence:     MIT
# -------------------------------------------------------------------------------

from spiderfoot import SpiderFootEvent, SpiderFootHelpers, SpiderFootPlugin


class sfp_email(SpiderFootPlugin):

    meta = {
        'name': "E-Mail Address Extractor",
        'summary': "Identify e-mail addresses in any obtained data.",
        'useCases': ["Passive", "Investigate", "Footprint"],
        'categories': ["Content Analysis"]
    }

    opts = {
        "max_emails": 100  # Limit total emails to prevent cascading
    }

    optdescs = {
        "max_emails": "Maximum number of email addresses to process (0 = unlimited)"
    }

    def setup(self, sfc, userOpts=dict()):
        self.sf = sfc
        self.email_count = 0

        for opt in userOpts.keys():
            self.opts[opt] = userOpts[opt]

    # What events is this module interested in for input
    def watchedEvents(self):
        return ["TARGET_WEB_CONTENT", "BASE64_DATA", "AFFILIATE_DOMAIN_WHOIS",
                "CO_HOSTED_SITE_DOMAIN_WHOIS", "DOMAIN_WHOIS", "NETBLOCK_WHOIS",
                "LEAKSITE_CONTENT", "RAW_DNS_RECORDS", "RAW_FILE_META_DATA",
                'RAW_RIR_DATA', "SIMILARDOMAIN_WHOIS",
                "SSL_CERTIFICATE_RAW", "SSL_CERTIFICATE_ISSUED", "TCP_PORT_OPEN_BANNER",
                "WEBSERVER_BANNER", "WEBSERVER_HTTPHEADERS"]

    # What events this module produces
    def producedEvents(self):
        return ["EMAILADDR", "EMAILADDR_GENERIC", "AFFILIATE_EMAILADDR"]

    # Handle events sent to this module
    def handleEvent(self, event):
        eventName = event.eventType
        srcModuleName = event.module
        eventData = event.data

        self.debug(f"Received event, {eventName}, from {srcModuleName}")
        
        # Check if we've reached the email limit
        max_emails = self.opts.get('max_emails', 100)
        if max_emails > 0 and self.email_count >= max_emails:
            self.debug(f"Reached maximum email limit ({max_emails}), skipping")
            return

        emails = SpiderFootHelpers.extractEmailsFromText(eventData)
        for email in set(emails):
            evttype = "EMAILADDR"
            email = email.lower()

            # Get the domain and strip potential ending .
            mailDom = email.split('@')[1].strip('.')
            if not self.sf.validHost(mailDom, self.opts['_internettlds']):
                self.debug(f"Skipping {email} as not a valid e-mail.")
                continue

            if not self.getTarget().matches(mailDom, includeChildren=True, includeParents=True) and not self.getTarget().matches(email):
                self.debug("External domain, so possible affiliate e-mail")
                evttype = "AFFILIATE_EMAILADDR"

            if eventName.startswith("AFFILIATE_"):
                evttype = "AFFILIATE_EMAILADDR"

            if not evttype.startswith("AFFILIATE_") and email.split("@")[0] in self.opts['_genericusers'].split(","):
                evttype = "EMAILADDR_GENERIC"

            self.info(f"Found e-mail address: {email}")
            mail = email.strip('.')
            
            # Increment email count
            self.email_count += 1

            evt = SpiderFootEvent(evttype, mail, self.__name__, event)
            if event.moduleDataSource:
                evt.moduleDataSource = event.moduleDataSource
            else:
                evt.moduleDataSource = "Unknown"
            self.notifyListeners(evt)
            
            # Check limit after notifying
            if max_emails > 0 and self.email_count >= max_emails:
                self.info(f"Reached maximum email limit ({max_emails}), stopping")
                break

# End of sfp_email class
