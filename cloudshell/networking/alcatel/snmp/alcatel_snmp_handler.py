#!/usr/bin/python
# -*- coding: utf-8 -*-

from cloudshell.devices.snmp_handler import SnmpHandler, SnmpContextManager

from cloudshell.networking.alcatel.flows.alcatel_disable_snmp_flow import AlcatelDisableSnmpFlow
from cloudshell.networking.alcatel.flows.alcatel_enable_snmp_flow import AlcatelEnableSnmpFlow
from cloudshell.networking.alcatel.snmp.alcatel_quali_snmp import AlcatelQualiSnmp


class AlcatelSnmpContextManager(SnmpContextManager):
    def __enter__(self):
        """
        Execute enable flow and create snmp service
        :return:
        :rtype: QualiSnmp
        """
        if self._enable_flow:
            self._enable_flow.execute_flow(self._snmp_parameters)
        return AlcatelQualiSnmp(self._snmp_parameters, self._logger)


class AlcatelSnmpHandler(SnmpHandler):
    def __init__(self, resource_config, logger, api, cli_handler):
        super(AlcatelSnmpHandler, self).__init__(resource_config, logger, api)
        self.cli_handler = cli_handler

    def _create_enable_flow(self):
        return AlcatelEnableSnmpFlow(self.cli_handler, self._logger)

    def _create_disable_flow(self):
        return AlcatelDisableSnmpFlow(self.cli_handler, self._logger)

    def get_snmp_service(self):
        """
        Enable/Disable snmp
        :param snmp_parameters:
        :return:
        :rtype: SnmpContextManager
        """
        return AlcatelSnmpContextManager(self.enable_flow, self.disable_flow,
                                   self._snmp_parameters, self._logger)