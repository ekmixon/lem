#!/usr/bin/python

from exploit_database import ExploitDatabase
from curation_manager import ExploitManager
from cve_manager import SecurityAPI

import sys
import subprocess
import re
import log
import shutil
import os


class Elem(object):
    def __init__(self, args):
        self.args = args
        self.logger = log.setup_custom_logger('elem')
        self.console_logger = log.setup_console_logger('console')

        self.exploitdb = ExploitDatabase(self.args.exploitdb,
                                         self.args.exploitdbrepo)
        self.exploit_manager = ExploitManager(self.args.exploits,
                                              self.args.exploitsrepo)

    def run(self):

        if hasattr(self.args, 'cpe') and 'Not Defined' in self.args.cpe:
            self.console_logger.error("CPE is required but not defined.")

        if hasattr(self.args, 'refresh'):
            self.refresh(self.args.securityapi, self.args.sslverify)
        elif hasattr(self.args, 'list'):
            self.list_exploits(self.args.edbid,
                               self.args.cveid)
        elif hasattr(self.args, 'score'):
            self.score_exploit(self.args.edbid,
                               self.args.cpe,
                               self.args.kind,
                               self.args.value)
        elif hasattr(self.args, 'assess'):
            self.assess()
        elif hasattr(self.args, 'copy'):
            self.copy(self.args.edbid, self.args.destination, self.args.stage, self.args.cpe)
        elif hasattr(self.args, 'patch'):
            self.patch(self.args.edbid)
        elif hasattr(self.args, 'setstage'):
            self.set_stage_info(self.args.edbid,
                                self.args.cpe,
                                self.args.command,
                                self.args.packages,
                                self.args.services,
                                self.args.selinux)

    def refresh(self,
                security_api_url,
                sslverify):
        self.console_logger.info("Refresh ExploitDB Repository")
        self.exploitdb.refresh_repository()
        self.console_logger.info("Finished Refreshing ExploitDB Repository")
        self.console_logger.info("Searching for CVE Information" +
                                 " in Known Exploits")
        self.exploitdb.refresh_exploits_with_cves()
        self.console_logger.info("Finished Searching for CVE Information" +
                                 " in Known Exploits")
        self.console_logger.info("Refreshing Exploits Repository")
        self.exploit_manager.refresh_repository()
        self.console_logger.info("Finished Refreshing Exploits Repository")
        self.exploit_manager.load_exploit_info()
        self.console_logger.info("Reconcile Existing Data with Data "
                                 "from ExploitDB")
        # We will reconcile information from the exploit database with the
        # existing exploit data.
        for edbid in self.exploitdb.exploits.keys():
            # Add an exploit if it doesn't exist
            if edbid not in self.exploit_manager.exploits.keys():
                self.exploit_manager.exploits[edbid] = dict(filename='',
                                                            cves=dict())
                self.exploit_manager.write(edbid)

            # Update the file name if necessary
            if self.exploit_manager.exploits[edbid]['filename'] != \
                    self.exploitdb.exploits[edbid]['filename']:
                self.exploit_manager.exploits[edbid]['filename'] = \
                    self.exploitdb.exploits[edbid]['filename']
                self.exploit_manager.write(edbid)


            # Ensure that all CVE's detected from exploit-db are present in
            # curation information.
            for cveid in self.exploitdb.exploits[edbid]['cves']:
                if cveid not in \
                        self.exploit_manager.exploits[edbid]['cves'].keys():
                    self.exploit_manager.exploits[edbid]['cves'][cveid] = \
                        dict()
                    self.exploit_manager.write(edbid)
        self.console_logger.info("Finished Reconciling Existing Data With "
                                 "Data from ExploitDB")
        # Next, query the security API
        self.console_logger.info("Refresh Data from SecurityAPI")
        securityapi = SecurityAPI(security_api_url, sslverify)
        securityapi.refresh()

        # Indicate whether a CVE was found in the security API or not
        for cve in securityapi.cve_list:
            for edbid in self.exploit_manager.exploits.keys():
                if cve in self.exploit_manager.exploits[edbid]['cves'].keys():
                    self.exploit_manager.exploits[edbid]['cves'][cve]['rhapi'] = True
                    self.exploit_manager.write(edbid)
        self.console_logger.info("Finished Refreshing Data from SecurityAPI")

    def list_exploits(self, edbids_to_find=[], cveids_to_find=[]):
        results = []
        try:
            self.exploit_manager.load_exploit_info()
        except OSError:
            self.console_logger.error("\nNo exploit information loaded.  "
                                      "Please try: elem refresh\n")
            sys.exit(1)

        for edbid_to_find in edbids_to_find:
            if self.exploit_manager.affects_el(edbid_to_find):
                results += self.exploit_manager.get_exploit_strings(edbid_to_find)
            else:
                self.console_logger.warn("Exploit ID %s does not appear "
                                         "to affect enterprise Linux." %
                                         edbid_to_find)
                sys.exit(0)

        for cveid_to_find in cveids_to_find:
            exploit_ids = self.exploit_manager.exploits_by_cve(cveid_to_find)
            for edbid in exploit_ids:
                results += self.exploit_manager.get_exploit_strings(edbid)
            if len(exploit_ids) == 0:
                self.console_logger.warn("There do not appear to be any "
                                         "exploits that affect CVE %s."
                                         % cveid_to_find)

        if not edbids_to_find and not cveids_to_find:
            for edbid in self.exploit_manager.exploits.keys():
                if self.exploit_manager.affects_el(edbid):
                    results += self.exploit_manager.get_exploit_strings(edbid)

        for line in results:
            self.console_logger.info(line)

        if len(results) == 0:
            self.console_logger.warn("There do not appear to be any "
                                     "exploit information available.  Please"
                                     " try: elem refresh")

    def score_exploit(self,
                      edbid,
                      cpe,
                      score_kind,
                      score):
        try:
            self.exploit_manager.load_exploit_info()
        except OSError:
            self.console_logger.error("\nNo exploit information loaded.  "
                                      "Please try: elem refresh\n")
            sys.exit(1)
        self.exploit_manager.score(edbid, cpe, score_kind, score)
        self.exploit_manager.write(edbid)

    def assess(self):
        assessed_cves = []
        lines = []
        error_lines = []

        try:
            self.exploit_manager.load_exploit_info()
        except OSError:
            self.console_logger.error("\nNo exploit information loaded.  "
                                      "Please try: elem refresh\n")
            sys.exit(1)

        try:
            command = ["yum", "updateinfo", "list", "cves"]
            p = subprocess.Popen(command,
                                 stdout=subprocess.PIPE,
                                 stderr=subprocess.PIPE)
            out, err = p.communicate()
            lines = out.split('\n')
            error_lines = err.split('\n')
        except OSError:
            self.logger.error("\'assess\' may only be "
                              "run on an Enterprise Linux host.")
            sys.exit(1)
        pattern = re.compile('\s(.*CVE-\d{4}-\d{4,})')
        for line in lines:
            result = re.findall(pattern, line)
            if result and result[0] not in assessed_cves:
                assessed_cves.append(result[0])

        assessed_cves = list(set(assessed_cves))

        for cveid in assessed_cves:
            edbids = self.exploit_manager.exploits_by_cve(cveid)
            for edbid in edbids:
                strings = self.exploit_manager.get_exploit_strings(edbid)
                for string in strings:
                    self.console_logger.info(string)

    def copy(self, edbids, destination, stage=False, cpe=''):
        dirname = os.path.dirname(os.path.realpath(__file__))

        try:
            self.exploit_manager.load_exploit_info()
        except OSError:
            self.console_logger.error("\nNo exploit information loaded.  "
                                      "Please try: elem refresh\n")
            sys.exit(1)

        for edbid in edbids:
            self.console_logger.info("Copying from %s to %s." %
                            (self.exploit_manager.exploits[edbid]['filename'],
                             destination))
            fullpath = os.path.join(self.exploitdb.content_path,
                                    self.exploit_manager.exploits[edbid]['filename'])
            shutil.copy(fullpath, destination)
            if stage and cpe is not '':
                success, msg = self.exploit_manager.stage(edbid,
                                                          destination,
                                                          cpe)
                if success:
                    self.console_logger.info("Successfuly staged exploit %s" %
                                             (edbid))
                else:
                    self.console_logger.info("Unsuccessfuly staged exploit " +
                                             "%s with error message %s." %
                                             (edbid, str(msg)))
            elif stage and cpe is '':
                self.console_logger.warn("CPE is undefined so unable to "
                                         "stage %s" % edbid)

    def patch(self, edbid):
        try:
            self.exploit_manager.load_exploit_info()
        except OSError:
            self.console_logger.error("\nNo exploit information loaded.  "
                                      "Please try: elem refresh\n")
            sys.exit(1)
        self.exploitdb.refresh_exploits_with_cves()
        lines = []
        error_lines = []
        cves_to_patch = ','.join(self.exploitdb.exploits[edbid]['cves'])

        try:
            self.console_logger.info("Patching system for EDB ID %s with "
                                     "CVE(s) %s." % (edbid, cves_to_patch))
            command = ["yum", "update", "-y", "--cve", cves_to_patch]
            p = subprocess.Popen(command,
                                 stdout=subprocess.PIPE,
                                 stderr=subprocess.PIPE)
            out, err = p.communicate()
            self.console_logger.info("Patching Completed.  A system restart" +
                                     "may be necessary.")
        except OSError:
            self.logger.error("\'assess\' may only be "
                              "run on an Enterprise Linux host.")

    def set_stage_info(self, edbid, cpe, command, packages, services, selinux):

        if not command and not packages and not services and not selinux:
            self.console_logger.error("At least one of the following must"
                                      "be specified for staging: command, "
                                      "packages, services, selinux")
            sys.exit(1)

        try:
            self.exploit_manager.load_exploit_info()
        except OSError:
            self.console_logger.error("\nNo exploit information loaded.  "
                                      "Please try: elem refresh\n")
            sys.exit(1)

        if command:
            self.console_logger.info("Setting stage command for %s to %s." %
                                     (edbid, command))
            self.exploit_manager.set_stage_info(edbid, cpe, command)
            self.exploit_manager.write(edbid)

        if packages:
            self.console_logger.info("Setting stage packages for %s to %s." %
                                     (edbid, packages))
            self.exploit_manager.add_packages(edbid, cpe, packages)
            self.exploit_manager.write(edbid)

        if services:
            self.console_logger.info("Setting stage services for %s to %s." %
                                     (edbid, services))
            self.exploit_manager.add_services(edbid, cpe, services)
            self.exploit_manager.write(edbid)

        if selinux:
            self.console_logger.info("Setting stage SELinux for %s to %s." %
                                     (edbid, selinux))
            self.exploit_manager.set_selinux(edbid, cpe, selinux)
            self.exploit_manager.write(edbid)
