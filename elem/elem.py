#!/usr/bin/python


from exploit_database import ExploitDatabase
from security_api import SecurityAPI
from cve import CVE

import sys
import subprocess
import re

class Elem(object):
    def __init__(self, args):
        self.args = args

    def run(self):

        if hasattr(self.args, 'refresh'):
            self.refresh(self.args.securityapi, self.args.api)
        elif hasattr(self.args, 'list'):
            self.list_exploits(self.args.edbid)
        elif hasattr(self.args, 'score'):
            self.score_exploit(self.args.edbid,
                               self.args.version,
                               self.args.spoof,
                               self.args.tampering,
                               self.args.repudiation,
                               self.args.infodisclosure,
                               self.args.dos,
                               self.args.escallation)
        elif hasattr(self.args, 'assess'):
            self.assess(self.args.csv)

    def refresh(self, security_api_url, query_api=False):
        exploitdb = ExploitDatabase()
        exploits = exploitdb.get_exploits_with_cves()

        securityapi = SecurityAPI()
        if query_api:
            securityapi.refresh(security_api_url)
        cve_list = securityapi.cve_list

        for cve in cve_list:
            for edbid in exploits.keys():
                if cve.id in exploits[edbid]['cves']:
                    cve.add_exploit(edbid, exploits[edbid]['filename'])
                    cve.write()


    def list_exploits(self, edbid=None):
        securityapi = SecurityAPI()
        cve_list = securityapi.cve_list
        for cve in cve_list:
            print dict(cve)

    def score_exploit(self, edbid, version, s, t, r, i, d, e):
        securityapi = SecurityAPI()
        cve_list = securityapi.cve_list
        for cve in cve_list:
            if cve.affected_by_exploit(edbid):
                cve.score_exploit(edbid, version, s, t, r, i, d, e)
                cve.write()

    def assess(self, csv=False):
        assessed_cves = []
        lines = []
        securityapi = SecurityAPI()
        try:
            try:
                lines = subprocess.check_output(["yum","updateinfo","list","cves"]).split('\n')
            except AttributeError:
                p = subprocess.Popen(["yum","updateinfo","list","cves"], stdout=subprocess.PIPE)
                out, err = p.communicate()
                lines = out.split('\n')
        except OSError:
            print "\'assess\' may only be run on an Enterprise Linux host."
            sys.exit(1)
        pattern = re.compile('\s(.*CVE-\d{4}-\d{4,})' )
        for line in lines:
            result = re.findall(pattern, line)
            if result and result[0] not in assessed_cves:
                assessed_cves.append(result[0])

        potential_exploits = securityapi.exploits_dict()
        for cve_id in assessed_cves:
            if cve_id in potential_exploits.keys():
                if not csv:
                    print cve_id, dict(potential_exploits[cve_id])
