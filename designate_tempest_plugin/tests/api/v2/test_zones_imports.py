# Copyright 2016 NEC Corporation.  All rights reserved.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

from oslo_log import log as logging
from tempest.lib import decorators
from tempest.lib import exceptions as lib_exc

from designate_tempest_plugin.common import waiters
from designate_tempest_plugin.tests import base
from designate_tempest_plugin.data_utils import rand_zone_name

LOG = logging.getLogger(__name__)


class BaseZonesImportTest(base.BaseDnsV2Test):
    excluded_keys = ['created_at', 'updated_at', 'version', 'links',
                     'status', 'message', 'zone_id']


class ZonesImportTest(BaseZonesImportTest):

    @classmethod
    def setup_credentials(cls):
        # Do not create network resources for these test.
        cls.set_network_resources()
        super(ZonesImportTest, cls).setup_credentials()

    @classmethod
    def setup_clients(cls):
        super(ZonesImportTest, cls).setup_clients()

        cls.client = cls.os_primary.zone_imports_client
        cls.zone_client = cls.os_primary.zones_client
        cls.recordset_client = cls.os_primary.recordset_client

    def generate_zonefile(self, name):
        return f"""$ORIGIN {name}\n
{name} 600 IN SOA ns1.{name} nsadmin.{name} (\n
    1  ; serial\n
    7200        ; refresh\n
    3600        ; retry\n
    2419200     ; expire\n
    10800       ; minimum\n
)\n
$TTL 7200\n
ipv4.{name}       300 IN A        192.0.0.1\n
ipv6.{name}       IN AAAA     fd00::1\n
cname.{name}      IN CNAME    {name}\n
{name}            IN MX       5   192.0.0.2\n
{name}            IN MX       10  192.0.0.3\n
_http._tcp.{name} IN SRV      10  0   80  192.0.0.4\n
_http._tcp.{name} IN SRV      10  5   80  192.0.0.5\n
{name}           IN TXT      abdef\n
{name}            IN SPF      "v=spf1 mx a"\n
{name}            IN NS       ns1.{name}\n
{name}            IN NS       ns2.{name}\n
delegation.{name} IN NS       ns1.{name}\n
1.0.0.192.in-addr.arpa. IN PTR      ipv4.{name}\n
"""

    def clean_up_resources(self, zone_import_id):
        waiters.wait_for_zone_import_status(self.client, zone_import_id,
                                            "COMPLETE")
        _, zone_import = self.client.show_zone_import(zone_import_id)
        self.client.delete_zone_import(zone_import['id'])
        self.wait_zone_delete(self.zone_client, zone_import['zone_id'])

    @decorators.idempotent_id('2e2d907d-0609-405b-9c96-3cb2b87e3dce')
    def test_create_zone_import(self):
        LOG.info('Create a zone import')
        _, zone_import = self.client.create_zone_import()
        self.addCleanup(self.clean_up_resources, zone_import['id'])

        LOG.info('Ensure we respond with PENDING')
        self.assertEqual('PENDING', zone_import['status'])

    @decorators.attr(type='smoke')
    @decorators.idempotent_id('c8909558-0dc6-478a-9e91-eb97b52e59e0')
    def test_show_zone_import(self):
        LOG.info('Create a zone import')
        _, zone_import = self.client.create_zone_import()
        self.addCleanup(self.clean_up_resources, zone_import['id'])

        LOG.info('Re-Fetch the zone import')
        resp, body = self.client.show_zone_import(zone_import['id'])

        LOG.info('Ensure the fetched response matches the expected one')
        self.assertExpected(zone_import, body, self.excluded_keys)

    @decorators.idempotent_id('56a16e68-b241-4e41-bc5c-c40747fa68e3')
    def test_delete_zone_import(self):
        LOG.info('Create a zone import')
        _, zone_import = self.client.create_zone_import()
        waiters.wait_for_zone_import_status(self.client, zone_import['id'],
                                            "COMPLETE")
        _, zone_import = self.client.show_zone_import(zone_import['id'])
        self.addCleanup(self.wait_zone_delete,
                        self.zone_client,
                        zone_import['zone_id'])

        LOG.info('Delete the zone')
        resp, body = self.client.delete_zone_import(zone_import['id'])

        LOG.info('Ensure successful deletion of imported zones')
        self.assertRaises(lib_exc.NotFound,
            lambda: self.client.show_zone_import(zone_import['id']))

    @decorators.idempotent_id('9eab76af-1995-485f-a2ef-8290c1863aba')
    def test_list_zones_imports(self):
        LOG.info('Create a zone import')
        _, zone_import = self.client.create_zone_import()
        self.addCleanup(self.clean_up_resources, zone_import['id'])

        LOG.info('List zones imports')
        _, body = self.client.list_zone_imports()

        self.assertGreater(len(body['imports']), 0)

    @decorators.idempotent_id('c2da410c-a505-42b4-a39c-51053e1319bc')
    def test_create_zone_import_force(self):
        LOG.info('Create a zone import')
        zone_name = rand_zone_name()
        zonefile_data = self.generate_zonefile(zone_name)
        _, zone_import = self.client.create_zone_import(force=True, zonefile_data=zonefile_data)
        self.addCleanup(self.clean_up_resources, zone_import['id'])
        waiters.wait_for_zone_import_status(self.client, zone_import['id'],
                                            "COMPLETE")
        _, zone_import = self.client.show_zone_import(zone_import['id'])
        _, recordsets = self.recordset_client.list_recordset(zone_import['zone_id'])
        records = [record for recordset in recordsets['recordsets'] for record in recordset['records']]
        self.assertEqual(len(records), 14)

    @decorators.idempotent_id('9d756a30-9110-41cb-b848-23f3bffc7649')
    def test_create_zone_update_force(self):
        LOG.info('Create a zone import')
        zone_name = rand_zone_name()
        zonefile_data = self.generate_zonefile(zone_name)
        _, zone_import = self.client.create_zone_import(zonefile_data=zonefile_data)
        self.addCleanup(self.clean_up_resources, zone_import['id'])
        waiters.wait_for_zone_import_status(self.client, zone_import['id'],
                                            "COMPLETE")
        _, zone_import = self.client.show_zone_import(zone_import['id'])
        LOG.info('Ensure zone import COMPLETE')
        self.assertEqual('COMPLETE', zone_import['status'])
        _, recordsets = self.recordset_client.list_recordset(zone_import['zone_id'])
        LOG.info('Create a zone import with force flag')
        new_zonefile = f"""$ORIGIN {zone_name}\n
{zone_name} 600 IN SOA ns1.{zone_name} nsadmin.{zone_name} (\n
    2  ; serial\n
    7200        ; refresh\n
    3600        ; retry\n
    2419200     ; expire\n
    10800       ; minimum\n
)\n
$TTL 7200
ipv4.{zone_name}       300 IN A        192.0.0.1\n
cname.{zone_name}      IN CNAME    {zone_name}\n
{zone_name}            IN MX       5   192.0.0.2\n
_http._tcp.{zone_name} IN SRV      10  0   80  192.0.0.4\n
{zone_name}            IN TXT      12345\n
{zone_name}            IN SPF      "v=spf1 mx a"\n
{zone_name}            IN NS       ns1.{zone_name}\n
delegation.{zone_name} IN NS       ns1.{zone_name}\n
1.0.0.192.in-addr.arpa. IN PTR      ipv4.{zone_name}\n
"""
        _, zone_import_new = self.client.create_zone_import(force=True, zonefile_data=new_zonefile)
        waiters.wait_for_zone_import_status(self.client, zone_import_new['id'],
                                            "COMPLETE")
        _, new_recordsets = self.recordset_client.list_recordset(zone_import['zone_id'])
        records = [record for recordset in new_recordsets['recordsets'] for record in recordset['records']]
        LOG.debug(f"Recordset records {records}")
        self.assertEqual(len(records), 11)
