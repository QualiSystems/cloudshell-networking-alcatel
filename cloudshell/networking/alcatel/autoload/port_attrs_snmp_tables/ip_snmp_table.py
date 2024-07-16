# from collections import defaultdict
# from threading import Thread
#
# from ipaddress import AddressValueError, IPv4Address, IPv6Address
# from codecs import decode
#
# from cloudshell.networking.alcatel.autoload.port_attrs_snmp_tables import port_constants
#
#
# class PortIPTables:
#     def __init__(self, snmp_service, logger):
#         self._snmp = snmp_service
#         self._logger = logger
#         self._ipv4_table = defaultdict(set)
#         self._ipv4_snmp_table = {}
#         self._ip_mixed_snmp_table = {}
#         self._ipv6_table = defaultdict(set)
#         self._ipv6_snmp_table = {}
#         self._thread_list = []
#
#     def load_snmp_table(self):
#         self._ipv4_snmp_table = self._snmp.walk(port_constants.PORT_OLD_IP_INDEXES)
#         if self._ipv4_snmp_table:
#             self._thread_list.append(
#                 Thread(
#                     target=self._convert_ipv4_table,
#                     name="IPv4 converter",
#                 )
#             )
#         self._ip_mixed_snmp_table = self._snmp.walk(
#             port_constants.PORT_MIXED_IP_INDEXES
#         )
#         if self._ip_mixed_snmp_table:
#             self._thread_list.append(
#                 Thread(
#                     target=self._convert_ip_mixed_table,
#                     name="Mixed IPs converter",
#                 )
#             )
#         self._ipv6_snmp_table = self._snmp.walk(port_constants.PORT_MIXED_IPV6_INDEXES)
#         if self._ipv6_snmp_table:
#             self._thread_list.append(
#                 Thread(
#                     target=self._convert_ipv6_table,
#                     name="IPv6 converter",
#                 )
#             )
#         [thread.start() for thread in self._thread_list]
#
#     def _convert_ipv4_table(self):
#         for ip in self._ipv4_snmp_table:
#             port_index = ip.safe_value
#             if port_index:
#                 self._ipv4_table[port_index].add(ip.index)
#
#     def _convert_ip_mixed_table(self):
#         for ip in self._ip_mixed_snmp_table:
#             port_index = ip.safe_value
#             if not port_index:
#                 continue
#             index = ip.index.replace("'", "")
#             if index.startswith("ipv6"):
#                 if index.startswith("ipv6z"):
#                     i = decode(index.replace("ipv6z.0x", ""), "hex").rstrip(b"\x00")
#                 else:
#                     i = decode(index.replace("ipv6.0x", ""), "hex")
#                 try:
#                     ipv6 = IPv6Address(i)
#                     self._ipv6_table[port_index].add(str(ipv6))
#                 except AddressValueError:
#                     self._logger.warning("Cannot convert {0} to IPv6 address".format(i))
#
#             elif index.startswith("ipv4"):
#                 if index.startswith("ipv4z"):
#                     i = decode(index.replace("ipv4z.0x", ""), "hex").rstrip(b"\x00")
#                 else:
#                     i = decode(index.replace("ipv4.0x", ""), "hex")
#
#                 try:
#                     ipv4 = IPv4Address(i)
#                     self._ipv4_table[port_index].add(str(ipv4))
#                 except AddressValueError:
#                     self._logger.warning("Cannot convert {0} to IPv4 address".format(i))
#
#     def _convert_ipv6_table(self):
#         for ipv6 in self._ipv6_snmp_table:
#             if ipv6.index:
#                 # ToDo check how the index looks like
#                 #  and use spilt in case "." occurs only once.
#                 index_location = ipv6.index.find(".")
#                 port_index = ipv6.index[:index_location]
#                 ipv6_address = ipv6.index.replace("{0}.".format(port_index), "")
#                 self._ipv6_table[port_index].add(ipv6_address)
#
#     def set_port_attributes(self, port_object):
#         port_object.ipv4_address = self.get_all_ipv4_by_index(
#             port_object.relative_address.native_index
#         )
#         port_object.ipv6_address = self.get_all_ipv6_by_index(
#             port_object.relative_address.native_index
#         )
#
#     def get_all_ipv4_by_index(self, port_index):
#         [thread.join() for thread in self._thread_list]
#         ip_addresses = self._ipv4_table.get(port_index)
#         if ip_addresses:
#             return ", ".join(ip_addresses)
#
#     def get_all_ipv6_by_index(self, port_index):
#         [thread.join() for thread in self._thread_list]
#         ip_addresses = self._ipv6_table.get(port_index)
#         if ip_addresses:
#             return ", ".join(ip_addresses)


from codecs import decode
from collections import defaultdict

# from cloudshell.snmp.core.domain.snmp_oid import SnmpMibObject
from ipaddress import AddressValueError, IPv4Address, IPv6Address

from threading import Thread


class PortIPTables:
    def __init__(self, snmp_service, logger):
        self._snmp = snmp_service
        self._logger = logger
        self._ipv4_table = defaultdict(set)
        self._ipv4_snmp_table = {}
        self._ip_mixed_snmp_table = {}
        self._ipv6_table = defaultdict(set)
        self._ipv6_snmp_table = {}
        self._thread_list = []

    def load_snmp_table(self):
        self._ipv4_snmp_table = self._snmp.get_bulk(("IP-MIB", "ipAdEntIfIndex"))
        if self._ipv4_snmp_table:
            self._thread_list.append(
                Thread(
                    target=self._convert_ipv4_table,
                    name="IPv4 converter",
                )
            )
        self._ip_mixed_snmp_table = self._snmp.get_bulk(
            ("IP-MIB", "ipAddressIfIndex")
        )
        if self._ip_mixed_snmp_table:
            self._thread_list.append(
                Thread(
                    target=self._convert_ip_mixed_table,
                    name="Mixed IPs converter",
                )
            )
        self._ipv6_snmp_table = self._snmp.get_bulk(("IPV6-MIB", "ipv6AddrType"))
        if self._ipv6_snmp_table:
            self._thread_list.append(
                Thread(
                    target=self._convert_ipv6_table,
                    name="IPv6 converter",
                )
            )
        [thread.start() for thread in self._thread_list]

    def _convert_ipv4_table(self):
        for ip, data in self._ipv4_snmp_table.iteritems():
            port_index = data.get("ipAdEntIfIndex")
            if port_index:
                self._ipv4_table[port_index].add(ip.index)

    def _convert_ip_mixed_table(self):
        for ip, data in self._ip_mixed_snmp_table.iteritems():
            port_index = data.get("ipAddressIfIndex")
            if not port_index:
                continue
            index = ip.replace("'", "")
            if index.startswith("ipv6"):
                if index.startswith("ipv6z"):
                    i = decode(index.replace("ipv6z.0x", ""), "hex").rstrip(b"\x00")
                else:
                    i = decode(index.replace("ipv6.0x", ""), "hex")
                try:
                    ipv6 = IPv6Address(i)
                    self._ipv6_table[port_index].add(str(ipv6))
                except AddressValueError:
                    self._logger.warning("Cannot convert {0} to IPv6 address".format(i))

            elif index.startswith("ipv4"):
                if index.startswith("ipv4z"):
                    i = decode(index.replace("ipv4z.0x", ""), "hex").rstrip(b"\x00")
                else:
                    i = decode(index.replace("ipv4.0x", ""), "hex")

                try:
                    ipv4 = IPv4Address(i)
                    self._ipv4_table[port_index].add(str(ipv4))
                except AddressValueError:
                    self._logger.warning("Cannot convert {0} to IPv4 address".format(
                        i))

    def _convert_ipv6_table(self):
        for ipv6 in self._ipv6_snmp_table:
            if ipv6:
                # ToDo check how the index looks like
                #  and use spilt in case "." occurs only once.
                index_location = ipv6.find(".")
                port_index = ipv6[:index_location]
                ipv6_address = ipv6.replace("{0}.".format(port_index), "")
                self._ipv6_table[port_index].add(ipv6_address)

    def set_port_attributes(self, port_object, port_index):
        port_object.ipv4_address = self.get_all_ipv4_by_index(
            port_index
        )
        port_object.ipv6_address = self.get_all_ipv6_by_index(
            port_index
        )

    def get_all_ipv4_by_index(self, port_index):
        [thread.join() for thread in self._thread_list]
        ip_addresses = self._ipv4_table.get(port_index)
        if ip_addresses:
            return ", ".join(ip_addresses)

    def get_all_ipv6_by_index(self, port_index):
        [thread.join() for thread in self._thread_list]
        ip_addresses = self._ipv6_table.get(port_index)
        if ip_addresses:
            return ", ".join(ip_addresses)

    def finalize_thread(self):
        try:
            [thread.join(0) for thread in self._thread_list]
        except:
            pass