from cloudshell.snmp.quali_snmp import QualiSnmp, QualiMibTable
from pysnmp.smi.rfc1902 import ObjectIdentity


class AlcatelQualiSnmp(QualiSnmp):
    def get_bulk(self, oid, retries=0, repetitions=25):
        """Bulk walk through the given table OID.

        :param oid: oid of the table to walk through.
        :param indices: only walk through the requested indices.
        :return: a dictionary of <index, <attribute, value>>
        """

        error_indication, error_status, error_index, self.var_binds = self.cmd_gen.bulkCmd(
            self.security,
            self.target,
            retries,
            repetitions,
            *(ObjectIdentity(*oid),)
        )

        oid_2_value = QualiMibTable(oid[1])
        for var_bind in self.var_binds:
            mibName, mib_value, suffix = self._translate_var_bind(var_bind[0])
            # We want table index to be numeric if possible.
            if str(suffix).isdigit():
                # Single index like 1, 2, 3... - treat as int
                index = int(str(suffix))
            else:
                # Triple or more index (like IPv4 in IP-Table) - treat as str.
                index = str(suffix)
            if not oid_2_value.get(index):
                oid_2_value[index] = {'suffix': str(suffix)}

            oid_2_value[index][mibName] = mib_value
            # self.logger.debug('{0}'.format(oid_2_value))

        return oid_2_value

    def get_selected_bulk(self, mib, oids, retries=0, repetitions=25):
        """Bulk walk through the given table OID.

        :param oid: oid of the table to walk through.
        :param indices: only walk through the requested indices.
        :return: a dictionary of <index, <attribute, value>>
        """

        for oid in oids:
            error_indication, error_status, error_index, _var_binds = self.cmd_gen.bulkCmd(
                self.security,
                self.target,
                retries,
                repetitions,
                *(ObjectIdentity(mib, oid),)
            )

            self.var_binds.extend(_var_binds)

        oid_2_value = QualiMibTable(oid[1])
        for var_bind in self.var_binds:
            mibName, mib_value, suffix = self._translate_var_bind(var_bind[0])
            # We want table index to be numeric if possible.
            if str(suffix).isdigit():
                # Single index like 1, 2, 3... - treat as int
                index = int(str(suffix))
            else:
                # Triple or more index (like IPv4 in IP-Table) - treat as str.
                index = str(suffix)
            if not oid_2_value.get(index):
                oid_2_value[index] = {'suffix': str(suffix)}

            oid_2_value[index][mibName] = mib_value
            # self.logger.debug('{0}'.format(oid_2_value))

        return oid_2_value