#!/usr/bin/python

# @Author: Rolind Roy <rolindroy>
# @Date:   2017-11-13T12:41:21+05:30
# @Email:  hello@rolindroy.com
# @Filename: monitoring.py
# @Last modified by:   rolindroy
# @Last modified time: 2017-11-14T17:05:51+05:30
# Openstack API Monitoring Script

import urllib2
import sys
import simplejson as json
import ConfigParser
import logging
import os
import time
import datetime

CONF_FILE = 'check_api.conf'
TOKEN_FILE = 'tokenfile'


class OSAPIMonitoring(object):

    def __init__(self, logger, config):
        self.logger = logger
        self.config = config
        self.username = self.config.get('api', 'user')
        self.password = self.config.get('api', 'password')
        self.tenant_name = self.config.get('api', 'tenant')
        self.default_endpoint = self.config.get('api', 'ip_api')
        self.endpoint_keystone = self.config.get('api', 'keystone_endpoints')
        self.services = self.config.get('api', 'service_list').split(',')

        self.zabbix_hostname = self.config.get('zabbix-server', 'hostname')
        self.zabbix_server = self.config.get('zabbix-server', 'server')

        self.token = None
        self.tenant_id = None
        self.tokenExp = False
        self.get_token()
        self.trigger = 0

    def get_timeout(self, service):
        return int(self.config.get('api', 'timeout'))

    def zabbix_trigger(self):
        self.logger.info("%s" % self.trigger)
        print(self.trigger)

    def get_token_from_file(self):
        if (os.path.exists('./' + TOKEN_FILE)):
            fileObj = open(TOKEN_FILE, "r")
            tokenData = fileObj.read()
            fileObj.close()
            if tokenData:
                fileToken, fileTenant, fileTimestamp = tokenData.split("|")
                currentTimestamp = time.mktime(
                    datetime.datetime.today().timetuple())
                if ((currentTimestamp - float(fileTimestamp)) < 3000):
                    self.token = fileToken
                    self.tenant_id = fileTenant
                else:
                    self.tokenExp = True
            else:
                self.tokenExp = True
        else:
            self.tokenExp = True
        return

    def set_token(self):
        if (self.token and self.tenant_id):
            fileObj = open(TOKEN_FILE, "w")
            writeData = self.token + "|" + self.tenant_id + "|" + \
                str(time.mktime(datetime.datetime.today().timetuple()))
            fileObj.write(writeData)
            fileObj.truncate()
            fileObj.close()
        return

    def get_token_from_keystone(self):
        data = json.dumps({
            "auth":
            {
                'tenantName': self.tenant_name,
                'passwordCredentials':
                {
                    'username': self.username,
                    'password': self.password
                }
            }
        })
        self.logger.info("Trying to get token from '%s'" % self.endpoint_keystone)
        fail_services = 0
        try:
            request = urllib2.Request(
                '%s/tokens' % self.endpoint_keystone,
                data=data,
                headers={
                    'Content-type': 'application/json'
                })

            data = json.loads(
                urllib2.urlopen(
                    request, timeout=self.get_timeout('keystone')).read())

            if len(data['access']['token']['id']) <= fail_services:
                self.trigger = 0
                return

            self.token = data['access']['token']['id']
            self.tenant_id = data['access']['token']['tenant']['id']
            # self.logger.debug("Got token '%s'" % self.token)
            self.trigger = 1
            return
        except Exception as e:
            self.logger.debug("Got exception '%s'" % e)
            self.trigger = 0

    def get_token(self):
        self.get_token_from_file()
        if (self.tokenExp == True):
            self.get_token_from_keystone()
            self.set_token()
        return

    def check_api(self, url, service):
        self.logger.info("Trying '%s' on '%s'" % (service, url))
        success_services = 0
        for x in range(0, 5):
            try:
                request = urllib2.Request(url,
                                          headers={
                                              'X-Auth-Token': self.token,
                                          })
                urllib2.urlopen(request, timeout=self.get_timeout(service))
                success_services = 1
            except Exception as e:
                self.logger.debug("Got exception from '%s' '%s'" % (service, e))
                self.trigger = 0

        if (success_services > 0):
            self.trigger = 1


def main():
    config = ConfigParser.RawConfigParser()
    config.read(CONF_FILE)

    logger = logging.getLogger()
    logging.basicConfig(filename='/tmp/rolind_python.log')
    # ch = logging.StreamHandler(sys.stdout)
    logger.setLevel(logging.DEBUG)
    # logger.addHandler(ch)

    API = OSAPIMonitoring(logger, config)

    if(len(sys.argv) > 1):
        if(sys.argv[1] == "keystone"):
            API.get_token_from_keystone()
        else:
            try:
                map = config.get('api', '%s_map' % sys.argv[1])
                url = 'http://%s:%s' % (API.default_endpoint, map)
                url = url % API.__dict__
                API.check_api(url, sys.argv[1])
            except Exception as e:
                self.logger.debug("Got exception from '%s' '%s'" % (service, e))
                API.trigger = 0
    else:
        API.trigger = 0

    API.zabbix_trigger()


if __name__ == "__main__":
    main()
