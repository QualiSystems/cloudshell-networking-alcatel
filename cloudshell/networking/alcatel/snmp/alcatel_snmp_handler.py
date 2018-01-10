#!/usr/bin/python
# -*- coding: utf-8 -*-

from cloudshell.networking.alcatel.cli.alcatel_cli_handler import AlcatelCliHandler
# from cloudshell.networking.alcatel.flows.alcatel_disable_snmp_flow import AlcatelDisableSnmpFlow
# from cloudshell.networking.alcatel.flows.alcatel_enable_snmp_flow import AlcatelEnableSnmpFlow
from cloudshell.devices.snmp_handler import SnmpHandler


class AlcatelSnmpHandler(SnmpHandler):
    def __init__(self, cli, resource_config, logger, api):
        super(AlcatelSnmpHandler, self).__init__(resource_config, logger, api)
        self._cli = cli
        self._api = api

    @property
    def cli_handler(self):
        return AlcatelCliHandler(self._cli, self.resource_config, self._logger, self._api)

    def _create_enable_flow(self):
        pass
        # return AlcatelEnableSnmpFlow(self.cli_handler, self._logger)

    def _create_disable_flow(self):
        pass
        # return AlcatelDisableSnmpFlow(self.cli_handler, self._logger)
