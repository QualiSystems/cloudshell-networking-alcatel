#!/usr/bin/python
# -*- coding: utf-8 -*-

import re
import os

from collections import defaultdict
from cloudshell.devices.autoload.autoload_builder import AutoloadDetailsBuilder
from cloudshell.devices.standards.networking.autoload_structure import *

from cloudshell.networking.alcatel.autoload.port_attrs_snmp_tables.ip_snmp_table import \
    PortIPTables


class ModuleHolder:
    def __init__(self, module_object, relative_path, structure_relative_path,
                 chassis_id):
        self.module_object = module_object
        self.relative_path = relative_path
        self.structure_relative_path = structure_relative_path
        self.chassis_id = chassis_id


class AlcatelGenericSNMPAutoload(object):
    HW_POSSIBLE_CLASSES = ["physChassis", "powerSupply", "ioModule", "xioModule",
                           "mdaModule"]

    def __init__(self, snmp_handler, shell_name, shell_type, resource_name, logger):
        """ Basic init with injected snmp handler and logger """

        self.snmp_handler = snmp_handler
        self.shell_name = shell_name
        self.shell_type = shell_type
        self.resource_name = resource_name
        self.logger = logger

        self.hw_data_dict = {}
        self.chassis_dict = {}
        self.power_supply_dict = {}
        self.io_modules_dict = {}
        self.xio_modules = []
        self.mda_modules = {}
        self.module_objects_map = {}
        self.chassis_objects_map = {}
        self.port_channel2ports = defaultdict(list)

        self.elements = {}
        self.resource = GenericResource(shell_name=shell_name,
                                        shell_type=shell_type,
                                        name=resource_name,
                                        unique_id=resource_name)

    def load_additional_mibs(self):
        """ Loads specific mibs inside snmp handler """

        # Path to General Alcatel MIBs
        path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "mibs"))
        self.snmp_handler.update_mib_sources(path)

    def discover(self, supported_os):
        """General entry point for autoload,
        read device structure and attributes: chassis, modules, submodules, ports, port-channels and power supplies

        :return: AutoLoadDetails object
        """

        if not self._is_valid_device_os(supported_os):
            raise Exception(self.__class__.__name__, 'Unsupported device OS')

        self.logger.info("*" * 70)
        self.logger.info("Start SNMP discovery process .....")

        self.load_additional_mibs()
        self.snmp_handler.load_mib(
            ["ATM-TC-MIB", "TIMETRA-CHASSIS-MIB", "TIMETRA-GLOBAL-MIB",
             "TIMETRA-PORT-MIB", "TIMETRA-TC-MIB"])

        self._get_device_details()

        self._load_snmp_tables()

        self._get_hw_data()
        self._get_chassis_info()
        self._get_power_ports_info()

        self._get_modules_info()
        self._get_ports_and_portchannels_info()

        autoload_details = AutoloadDetailsBuilder(self.resource).autoload_details()
        self._log_autoload_details(autoload_details)
        return autoload_details

    def _is_valid_device_os(self, supported_os):
        """Validate device OS using snmp
            :return: True or False
        """

        system_description = self.snmp_handler.get_property('SNMPv2-MIB', 'sysDescr',
                                                            '0')
        self.logger.debug(
            'Detected system description: \'{0}\''.format(system_description))
        result = re.search(r"({0})".format("|".join(supported_os)),
                           system_description,
                           flags=re.DOTALL | re.IGNORECASE)

        if result:
            return True
        else:
            error_message = 'Incompatible driver! Please use this driver for \'{0}\' operation system(s)'. \
                format(str(tuple(supported_os)))
            self.logger.error(error_message)
            return False

    def _get_device_details(self):
        """ Get root element attributes """

        self.logger.info("Building Root")
        vendor = "Alcatel"

        self.resource.contact_name = self.snmp_handler.get_property('SNMPv2-MIB',
                                                                    'sysContact', '0')
        self.resource.system_name = self.snmp_handler.get_property('SNMPv2-MIB',
                                                                   'sysName', '0')
        self.resource.location = self.snmp_handler.get_property('SNMPv2-MIB',
                                                                'sysLocation', '0')
        self.resource.os_version = self._get_device_os_version()
        self.resource.model = self._get_device_model()
        self.resource.vendor = vendor

    def _get_device_model(self):
        """ Get device model form snmp SNMPv2 mib

        :return: device model
        :rtype: str
        """

        result = ''

        match_name = re.search(r'::(?P<model>\S+$)',
                               self.snmp_handler.get_property('SNMPv2-MIB',
                                                              'sysObjectID', '0'))
        if match_name:
            result = match_name.groupdict()['model']
        return re.sub(r".*model", "", result, flags=re.IGNORECASE)

    def _get_device_os_version(self):
        """ Get device OS Version form snmp SNMPv2 mib

        :return: device model
        :rtype: str
        """

        result = ""
        matched = re.search(r"TiMOS\S+?(?P<os_version>\d+\S+)\s",
                            self.snmp_handler.get_property('SNMPv2-MIB', 'sysDescr',
                                                           '0'), re.IGNORECASE)
        if matched:
            result = matched.groupdict().get("os_version", "")
        return result

    def _load_snmp_tables(self):
        """ Load all required SNMP tables """

        self.logger.info('Start loading MIB tables:')
        self.lldp_local_table = self.snmp_handler.get_table('LLDP-MIB',
                                                            'lldpLocPortDesc')
        self.lldp_remote_table = self.snmp_handler.get_table('LLDP-MIB', 'lldpRemTable')
        self.ip_table = PortIPTables(self.snmp_handler, self.logger)
        self.ip_table.load_snmp_table()

        for item in self.snmp_handler.get_table('IEEE8023-LAG-MIB',
                                                'dot3adAggPortAttachedAggID').values():
            if item["dot3adAggPortAttachedAggID"] != "0":
                self.port_channel2ports[item["dot3adAggPortAttachedAggID"]].append(
                    item["suffix"])

        self.logger.info('MIB Tables loaded successfully')

    def _get_hw_data(self):
        """ Read TIMETRA-CHASSIS-MIB and filter out device's structure and elements like chassis, modules, power ports
        """

        self.hw_data_dict = self.snmp_handler.get_selected_bulk("TIMETRA-CHASSIS-MIB",
                                                  ["tmnxHwName",
                                                   "tmnxHwClass",
                                                   "tmnxHwContainedIn",
                                                   "tmnxHwParentRelPos",
                                                   "tmnxHwAdminState",
                                                   "tmnxHwOperState",
                                                   "tmnxHwSerialNumber",
                                                   "tmnxHwSoftwareCodeVersion"
                                                   ]
                                                  )
        res = {k: {
            kk: vv.strip("'") for kk, vv in v.iteritems()
        } for k, v in self.hw_data_dict.iteritems() if v.get("tmnxHwClass", "").replace("'", "") in
                                         self.HW_POSSIBLE_CLASSES
        }
        for index, attrs in res.iteritems():
            hw_class = attrs["tmnxHwClass"].lower()

            allowed_states = ("inService", "provisioned")
            admin_state = attrs["tmnxHwAdminState"]
            oper_state = attrs["tmnxHwOperState"]

            # discover only working devices
            if admin_state in allowed_states and oper_state in allowed_states:

                if hw_class == "physchassis":
                    self.chassis_dict[index] = attrs
                elif hw_class == "powersupply":
                    self.power_supply_dict[index] = attrs
                elif hw_class == "iomodule":
                    self.io_modules_dict[index] = attrs
                elif hw_class == "xiomodule":
                    self.io_modules_dict[index] = attrs
                    self.xio_modules.append(index)
                elif hw_class == "mdamodule":
                    self.mda_modules[index] = attrs
                else:
                    continue

    def _get_chassis_info(self):
        """ Get Chassis element attributes """

        self.logger.info("Building Chassis")

        for chassis_index, attrs in self.chassis_dict.iteritems():
            chassis_id = str(self.chassis_dict.keys().index(chassis_index) + 1)
            # chassis_id = chassis_index.split(".")[0]
            chassis_name = "Chassis {}".format(chassis_id)
            chassis_hw_name = self.hw_data_dict[chassis_index].get(
                    "tmnxHwName", "")
            if "chassis" in chassis_hw_name.lower():
                chassis_name = chassis_hw_name
            elif "esat" in chassis_hw_name:
                chassis_name = chassis_hw_name
                # chassis_id = chassis_hw_name.rsplit("-")[-1]

            chassis_object = GenericChassis(shell_name=self.shell_name,
                                            name=chassis_name,
                                            unique_id="{}.{}.{}".format(
                                                self.resource_name, "chassis",
                                                chassis_index))

            chassis_object.serial_number = attrs.get("tmnxHwSerialNumber", "")

            chassis_type_id = self.snmp_handler.get_property("TIMETRA-CHASSIS-MIB",
                                                             "tmnxChassisType",
                                                             chassis_index)
            chassis_object.model = self.snmp_handler.get_property("TIMETRA-CHASSIS-MIB",
                                                                  "tmnxChassisTypeDescription",
                                                                  chassis_type_id)

            self._add_element(relative_path=chassis_id, resource=chassis_object)
            if "esat" in chassis_name:
                new_ch_name = chassis_hw_name.lower().replace("chassis", "").strip()
                self.chassis_objects_map[new_ch_name] = chassis_object
            else:
                self.chassis_objects_map[chassis_id] = chassis_object

        self.logger.info("Building Chassis completed")

    def _get_parent_ids(self, item_index):
        pos_id = self.hw_data_dict[item_index].get("tmnxHwParentRelPos")
        contained_in_id = self.hw_data_dict[item_index]["tmnxHwContainedIn"]
        chassis_id = item_index.split(".", 1)[0]
        if contained_in_id == "0":
            return [chassis_id]

        contained_in_id = "{}.{}".format(chassis_id, contained_in_id)
        return self._get_parent_ids(contained_in_id) + [pos_id]

    def _get_power_ports_info(self):
        """ Get power port elements attributes """

        self.logger.info("Start loading Power Ports")

        for index, attrs in self.power_supply_dict.items():
            pp_ids = self._get_parent_ids(
                index)  # [<Chassis id>, <PowerShelf id>, <Power Port id>]
            pp_name = "PP {0}".format('-'.join(pp_ids[1:]))

            power_port_object = GenericPowerPort(
                shell_name=self.shell_name,
                name=pp_name,
                unique_id="{0}.{1}.{2}".format(self.resource_name, "power_port",
                                               '.'.join(pp_ids)),
            )
            # TODO
            power_port_object.model = ""
            power_port_object.port_description = ""
            power_port_object.version = ""
            power_port_object.serial_number = attrs["tmnxHwSerialNumber"]

            self._add_element(
                relative_path="{}/{}".format(pp_ids[0], pp_name),
                resource=power_port_object,
            )

        self.logger.info("Building Power Ports completed")

    def _get_modules_info(self):
        """ Set attributes for all discovered modules """

        self.logger.info("Building Modules")

        self.logger.info("Building IO Modules")

        for index, attrs in self.io_modules_dict.items():
            module_ids = self._get_parent_ids(index)
            card_index = ".".join(module_ids)
            io_rel_path = "/".join(module_ids)
            if index in self.xio_modules:
                chassis_id = module_ids[0]
                module_ids = [chassis_id]
                xio_module_ids = self.hw_data_dict[index].get(
                    "tmnxHwName", "").replace("XIOM", "").strip(" ")
                module_ids.append(xio_module_ids.replace("/", "-"))
                io_rel_path = "{0}/{1}".format(chassis_id, xio_module_ids)

            if len(module_ids) < 2:
                self.logger.error(
                    "Impossible to determine IO Module parent. Module HwIndex: {}".format(
                        index))
                continue
            elif len(module_ids) == 2:
                module_id = module_ids[-1]
                module_object = GenericModule(
                    shell_name=self.shell_name,
                    name="Module {}".format(module_id),
                    unique_id="{0}.{1}.{2}".format(self.resource_name, "module",
                                                   ".".join(module_ids)))
            else:
                module_id = module_ids[-1]
                module_object = GenericSubModule(
                    shell_name=self.shell_name,
                    name="SubModule {}".format(module_id),
                    unique_id="{0}.{1}.{2}".format(self.resource_name, "sub_module",
                                                   ".".join(module_ids)))

            module_object.serial_number = attrs.get("tmnxHwSerialNumber", "")
            module_type_id = self.snmp_handler.get_property("TIMETRA-CHASSIS-MIB",
                                                            "tmnxCardEquippedType",
                                                            card_index)
            module_object.model = self.snmp_handler.get_property("TIMETRA-CHASSIS-MIB",
                                                                 "tmnxCardTypeDescription",
                                                                 module_type_id)

            module_object.version = attrs.get("tmnxHwSoftwareCodeVersion", "")
            self.module_objects_map[io_rel_path] = ModuleHolder(module_object,
                                                                "/".join(module_ids),
                                                                io_rel_path,
                                                                module_ids[0])
            # self._add_element(relative_path=io_rel_path,
            #                   resource=module_object)

        self.logger.info("Building MDA Modules")
        for index, attrs in self.mda_modules.items():
            module_ids = self._get_parent_ids(index)
            card_index = ".".join(module_ids)
            rel_path = "/".join(module_ids)
            actual_module_ids = self.hw_data_dict[index].get("tmnxHwName", "").replace(
                    "MDA", "").strip(" ")
            if actual_module_ids and "/".join(module_ids) not in actual_module_ids:
                actual_module_ids_list = actual_module_ids.replace(
                    "/", "-", 1).split("/")
                chassis_id = module_ids[0]
                module_ids = [chassis_id] + actual_module_ids_list
                rel_path = "{0}/{1}".format(chassis_id, actual_module_ids)

            if len(module_ids) < 2:
                self.logger.error(
                    "Impossible to determine IO Module parent. "
                    "Module HwIndex: {}".format(index)
                )
                continue
            elif len(module_ids) == 2:
                module_id = module_ids[-1]
                module_object = GenericModule(
                    shell_name=self.shell_name,
                    name="Module {}".format(module_id),
                    unique_id="{0}.{1}.{2}".format(self.resource_name, "module",
                                                   ".".join(module_ids)))
            else:
                module_id = module_ids[-1]
                module_object = GenericSubModule(
                    shell_name=self.shell_name,
                    name="SubModule {}".format(module_id),
                    unique_id="{0}.{1}.{2}".format(self.resource_name, "sub_module",
                                                   ".".join(module_ids)))

            module_object.serial_number = attrs.get("tmnxHwSerialNumber", "")

            module_type_id = self.snmp_handler.get_property("TIMETRA-CHASSIS-MIB",
                                                            "tmnxCardEquippedType",
                                                            card_index)
            module_object.model = self.snmp_handler.get_property("TIMETRA-CHASSIS-MIB",
                                                                 "tmnxMdaTypeDescription",
                                                                 module_type_id)

            module_object.version = ""
            self.module_objects_map[rel_path] = ModuleHolder(module_object,
                                                                "/".join(module_ids),
                                                                rel_path,
                                                                module_ids[0])
            # self._add_element(relative_path=rel_path,
            #                   resource=module_object)

        self.logger.info("Building Modules completed")

    def _get_ports_and_portchannels_info(self):
        """ Get port and port channel elements attributes """

        self.logger.info("Building Ports and PortChannels")

        port_pattern = re.compile(
            r'^(\S*\d+/)*(?P<sfp_port>[a-zA-Z])?\d+/\d+$')  # 1/1/4 or 1/1/c2/1

        port_hw_table = self.snmp_handler.get_table('TIMETRA-PORT-MIB',
                                                    'tmnxPortName').values()
        port_ifindex2name = {port_data.get("suffix").split(".")[-1]: "Port {}".format(
            port_data.get("tmnxPortName")) for
            port_data in port_hw_table}

        for port_data in port_hw_table:
            port_name = port_data.get("tmnxPortName")
            port_hw_index = port_data.get("suffix")
            chassis_index, if_index = port_hw_index.split(".")
            port_match = port_pattern.match(port_name)

            if "lag" in port_name:  # Check if it is portchannel
                port_channel = GenericPortChannel(shell_name=self.shell_name,
                                                  name=port_name.replace("/", "-"),
                                                  unique_id="{0}.{1}.{2}".format(
                                                      self.resource_name,
                                                      "port_channel",
                                                      if_index))

                port_channel.port_description = self.snmp_handler.get_property(
                    "TIMETRA-PORT-MIB",
                    "tmnxPortDescription",
                    port_hw_index).strip("'")
                self.ip_table.set_port_attributes(port_channel, if_index)
                port_channel.associated_ports = self._get_associated_ports(if_index,
                                                                           port_ifindex2name)

                # TODO Fix relative path
                self._add_element(relative_path=if_index, resource=port_channel)
                self.logger.info("Added PortChannel '{}'".format(port_channel.name))
            elif port_match:
                if port_match.group('sfp_port'):
                    port_name = '-'.join(
                        port_name.rsplit('/', 1))  # replace last "/" with "-"

                port_object = GenericPort(shell_name=self.shell_name,
                                          name="Port {}".format(
                                              port_name.replace("/", "-")),
                                          unique_id="{0}.{1}.{2}".format(
                                              self.resource_name,
                                              "port",
                                              if_index))

                port_object.port_description = self.snmp_handler.get_property(
                    "TIMETRA-PORT-MIB",
                    "tmnxPortDescription",
                    port_hw_index).strip("'")

                port_object.l2_protocol_type = self.snmp_handler.get_property("IF-MIB",
                                                                              "ifType",
                                                                              if_index).strip(
                    "'")
                port_object.mac_address = self.snmp_handler.get_property("IF-MIB",
                                                                         "ifPhysAddress",
                                                                         if_index).strip(
                    "'")
                port_object.mtu = self.snmp_handler.get_property("IF-MIB", "ifMtu",
                                                                 if_index)
                port_object.bandwidth = self.snmp_handler.get_property("IF-MIB",
                                                                       "ifHighSpeed",
                                                                       if_index)

                self.ip_table.set_port_attributes(port_object, if_index)

                port_object.duplex = self._get_duplex(port_hw_index)
                port_object.auto_negotiation = self._get_auto_negotiation(port_hw_index)
                port_object.adjacent = ""
                # port_object.adjacent = self._get_adjacent(port_hw_index)
                if "esat" in port_object.name:
                    port_indexes = port_name.split("/")
                    chassis_obj = self.chassis_objects_map.get(port_indexes[0])
                    if chassis_obj:
                        rel_path = re.search(r"\d+", port_indexes[-1]).group()
                        chassis_obj.add_sub_resource(rel_path, port_object)
                    continue
                self._add_port_element(
                    relative_path="{}/{}".format(chassis_index, port_name),
                    resource=port_object)
                self.logger.info("Added Interface '{}'".format(port_object.name))

        self.logger.info("Building Ports and PortChannels completed")

    def _get_associated_ports(self, port_channel_id, ifindex2name_mapping):
        """ Get all ports associated with provided port channel """

        port_names = []
        for port_if_index in self.port_channel2ports.get(port_channel_id, []):
            port_names.append(ifindex2name_mapping.get(port_if_index).strip(' \t\n\r'))

        return "; ".join(port_names)

    def _get_duplex(self, port_hw_id):
        """ Determine interface duplex

            :return: Full or Half
        """

        if self.snmp_handler.get_property("TIMETRA-PORT-MIB",
                                          "tmnxPortEtherDuplex",
                                          port_hw_id).strip("'") == "fullDuplex" or \
                self.snmp_handler.get_property("TIMETRA-PORT-MIB",
                                               "tmnxPortEtherOperDuplex",
                                               port_hw_id).strip("'") == "fullDuplex":
            return "Full"

        return "Half"

    def _get_auto_negotiation(self, port_hw_id):
        """ Determine interface auto negotiation

        :return: "True" or "False"
        """

        if self.snmp_handler.get_property("TIMETRA-PORT-MIB",
                                          "tmnxPortEtherAutoNegotiate",
                                          port_hw_id).strip("'") == "true":
            return "True"

        return "False"

    def _add_module_recursive(self, module):
        """ Add module object data to resources and attributes lists """
        if module.structure_relative_path in self.elements:
            return
        # rel_seq = module.structure_relative_path.rsplit("/", 1)
        rel_seq = module.relative_path.rsplit("/", 1)
        parent_id = rel_seq[0].split("-")[0]

        if parent_id:
            if parent_id == module.chassis_id:
                parent_object = self.elements.get(parent_id, None)
                parent_object.add_sub_resource(re.search(r"\d+", rel_seq[
                    -1]).group(), module.module_object)
                self.elements.update({module.structure_relative_path: module.module_object})
                return

            parent = self.module_objects_map.get(parent_id)
            parent_object = parent.module_object
            if parent.structure_relative_path not in self.elements:
                self._add_module_recursive(parent)

            parent_object.add_sub_resource(
                re.search(r"\d+", rel_seq[-1]).group(),
                module.module_object
            )
            self.elements.update(
                {module.structure_relative_path: module.module_object}
            )

    def _add_port_element(self, relative_path, resource):
        """ Add port object data to resources and attributes lists """
        if not relative_path:
            self.logger.error("Failed to add {0} port".format(resource.name))
            return
        rel_seq = relative_path.rsplit("/", 1)
        parent = self.module_objects_map.get(rel_seq[0])
        if parent:
            if rel_seq[0] not in self.elements:
                self._add_module_recursive(parent)

            parent.module_object.add_sub_resource(
                re.search(r"\d+", rel_seq[-1]).group(),
                resource
            )
            self.elements.update({relative_path.replace("-", "/"): resource})
        else:
            self._add_port_element(rel_seq[0], resource)

    def _add_element(self, relative_path, resource, parent_id=""):
        """Add object data to resources and attributes lists

        :param resource: object which contains all required data for certain resource
        """

        rel_seq = relative_path.split("/")

        if len(rel_seq) == 1:  # Chassis and PortChannel connected directly to root
            parent_object = self.resource
            rel_path = relative_path
        else:
            if parent_id:
                parent_object = self.elements.get(parent_id, None)
            else:
                parent_object = self.elements.get("/".join(rel_seq[:-1]), None)

            rel_path = re.search(r"\d+", rel_seq[-1]).group()

        if parent_object:
            parent_object.add_sub_resource(rel_path, resource)
            self.elements.update({relative_path: resource})

    def _log_autoload_details(self, autoload_details):
        """
        Logging autoload details
        :param autoload_details:
        :return:
        """
        self.logger.debug("-------------------- <RESOURCES> ----------------------")
        for resource in autoload_details.resources:
            self.logger.debug(
                "{0:15}, {1:20}, {2}".format(resource.relative_address, resource.name,
                                             resource.unique_identifier))
        self.logger.debug("-------------------- </RESOURCES> ----------------------")

        self.logger.debug("-------------------- <ATTRIBUTES> ---------------------")
        for attribute in autoload_details.attributes:
            self.logger.debug(
                "-- {0:15}, {1:60}, {2}".format(attribute.relative_address,
                                                attribute.attribute_name,
                                                attribute.attribute_value))
        self.logger.debug("-------------------- </ATTRIBUTES> ---------------------")
