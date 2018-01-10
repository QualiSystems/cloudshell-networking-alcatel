#!/usr/bin/python
# -*- coding: utf-8 -*-

from cloudshell.devices.runners.autoload_runner import AutoloadRunner

from cloudshell.networking.alcatel.flows.alcatel_autoload_flow import AlcatelSnmpAutoloadFlow
from cloudshell.networking.alcatel.snmp.alcatel_snmp_handler import AlcatelSnmpHandler


class AlcatelAutoloadRunner(AutoloadRunner):
    def __init__(self, cli, logger, resource_config, api):
        super(AlcatelAutoloadRunner, self).__init__(resource_config)
        self._cli = cli
        self._api = api
        self._logger = logger

    @property
    def snmp_handler(self):
        return AlcatelSnmpHandler(self._cli, self.resource_config, self._logger, self._api)

    @property
    def autoload_flow(self):
        return AlcatelSnmpAutoloadFlow(self.snmp_handler, self._logger)
