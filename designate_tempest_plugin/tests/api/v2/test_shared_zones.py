# Copyright 2020 Cloudification GmbH. All rights reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.

from oslo_log import log as logging
from oslo_utils import uuidutils
from tempest import config
from tempest.lib.common.utils import data_utils
from tempest.lib import decorators
from tempest.lib import exceptions as lib_exc

from designate_tempest_plugin.tests import base
from designate_tempest_plugin import data_utils as dns_data_utils

LOG = logging.getLogger(__name__)

CONF = config.CONF


class BaseSharedZoneTest(base.BaseDnsV2Test):
    credentials = ['primary', 'admin', 'alt', ['demo']]

    excluded_keys = ['links']

    @classmethod
    def setup_credentials(cls):
        cls.set_network_resources()
        super(BaseSharedZoneTest, cls).setup_credentials()

    @classmethod
    def resource_setup(cls):
        super(BaseSharedZoneTest, cls).resource_setup()
        # All the shared zone tests need a zone, create one to share
        zone_name = dns_data_utils.rand_zone_name(name="testdomain")
        LOG.info('Create a zone: %s', zone_name)
        cls.zone = cls.zones_client.create_zone(name=zone_name)[1]

    @classmethod
    def resource_cleanup(cls):
        cls.zones_client.delete_zone(
            cls.zone['id'], ignore_errors=lib_exc.NotFound, delete_shares=True)
        super(BaseSharedZoneTest, cls).resource_cleanup()

    @classmethod
    def setup_clients(cls):
        super(BaseSharedZoneTest, cls).setup_clients()
        cls.zones_client = cls.os_primary.zones_client
        cls.share_zone_client = cls.os_primary.shared_zones_client
        cls.adm_shr_client = cls.os_admin.shared_zones_client
        cls.adm_zones_client = cls.os_admin.zones_client
        cls.alt_zone_client = cls.os_alt.zones_client
        cls.demo_zone_client = cls.os_demo.zones_client
        cls.alt_share_zone_client = cls.os_alt.shared_zones_client


class SharedZonesTest(BaseSharedZoneTest):
    credentials = ['primary', 'admin', 'alt', ['demo']]

    @classmethod
    def setup_credentials(cls):
        # Do not create network resources for these test.
        cls.set_network_resources()
        super(SharedZonesTest, cls).setup_credentials()

    @decorators.idempotent_id('982a7780-a460-4c13-97df-b4855bf19c7b')
    def test_create_zone_share(self):
        # Test a basic API create a zone share
        shared_zone = self.share_zone_client.create_zone_share(
            self.zone['id'], self.alt_zone_client.project_id)[1]
        self.addCleanup(self.share_zone_client.delete_zone_share,
                        self.zone['id'], shared_zone['id'])

        self.assertTrue(uuidutils.is_uuid_like(shared_zone['id']))
        self.assertEqual(self.zone['id'], shared_zone['zone_id'])
        self.assertEqual(self.share_zone_client.project_id,
                         shared_zone['project_id'])
        self.assertEqual(self.alt_zone_client.project_id,
                         shared_zone['target_project_id'])
        self.assertIsNotNone(shared_zone['created_at'])
        self.assertIsNone(shared_zone['updated_at'])
        self.assertIsNotNone(shared_zone['links'])

    @decorators.idempotent_id('0edecb9b-4890-433c-8195-0935271efc9a')
    def test_show_shared_zone(self):
        shared_zone = self.share_zone_client.create_zone_share(
            self.zone['id'], self.alt_zone_client.project_id)[1]
        self.addCleanup(self.share_zone_client.delete_zone_share,
                        self.zone['id'], shared_zone['id'])

        # Test show zone share
        LOG.info('Fetch the zone share')
        body = self.share_zone_client.show_zone_share(self.zone['id'],
                                                      shared_zone['id'])[1]

        LOG.info('Ensure the fetched response matches the zone share')
        self.assertExpected(shared_zone, body, self.excluded_keys)

    @decorators.idempotent_id('a18a8577-9d02-492a-a869-4ff7d6f4f89b')
    def test_delete_zone_share(self):
        shared_zone = self.share_zone_client.create_zone_share(
            self.zone['id'], self.alt_zone_client.project_id)[1]
        self.addCleanup(self.share_zone_client.delete_zone_share,
                        self.zone['id'], shared_zone['id'],
                        ignore_errors=lib_exc.NotFound)

        # Test zone share delete
        LOG.info('Delete zone share')
        self.share_zone_client.delete_zone_share(self.zone['id'],
                                                 shared_zone['id'])

        LOG.info('Ensure the zone share was deleted')
        self.assertRaises(lib_exc.NotFound,
                          self.share_zone_client.show_zone_share,
                          self.zone['id'], shared_zone['id'])

    @decorators.idempotent_id('55a44bbe-e14d-4d2a-9421-9980898a0b1d')
    def test_list_shares(self):
        shares = self.share_zone_client.list_shares()
        LOG.info(f"List of shares {shares}")
        self.assertNotEmpty(shares[1]['shared_zones'])

    @decorators.idempotent_id('1b4fc7bc-4d1d-43e5-a98f-5052665eeb5d')
    def test_list_shares_zone_id_param(self):
        zone_name = dns_data_utils.rand_zone_name(name="testdomain")
        zone = self.adm_zones_client.create_zone(name=zone_name)[1]
        self.addCleanup(self.adm_zones_client.delete_zone,
                        zone['id'], delete_shares=True)
        shared_zone = self.adm_shr_client.create_zone_share(
            zone['id'], self.alt_zone_client.project_id)[1]
        self.addCleanup(self.adm_shr_client.delete_zone_share,
                        zone['id'], shared_zone['id'])

        # List of shares by zone id
        params = {"zone_id": zone['id']}
        shares = self.adm_shr_client.list_shares(params=params)[1]
        LOG.info(f"List of shares {shares} for zone {zone}")
        self.assertEqual(1, len(shares['shared_zones']))

    @decorators.idempotent_id('21cfced2-a31d-43cd-93e9-33e7c31b7172')
    def test_list_shares_tenant_id_param(self):
        zone_name = dns_data_utils.rand_zone_name(name="testdomain")
        zone = self.adm_zones_client.create_zone(name=zone_name)[1]
        self.addCleanup(self.adm_zones_client.delete_zone,
                        zone['id'], delete_shares=True)
        shared_zone = self.adm_shr_client.create_zone_share(
            zone['id'], self.alt_zone_client.project_id)[1]
        self.addCleanup(self.adm_shr_client.delete_zone_share,
                        zone['id'], shared_zone['id'])

        shared_zone_demo = self.adm_shr_client.create_zone_share(
            zone['id'], self.demo_zone_client.project_id)[1]
        self.addCleanup(self.adm_shr_client.delete_zone_share,
                        zone['id'], shared_zone_demo['id'])

        LOG.info('List zone shares for project id param')
        params = {
                  'target_project_id': self.demo_zone_client.project_id
                  }
        body = self.adm_shr_client.list_shares(params=params)[1]
        filtered_shares = [
            share for share in body['shared_zones']
            if share['zone_id'] == zone['id']
        ]
        self.assertEqual(1, len(filtered_shares))

    @decorators.idempotent_id('56157e02-75dc-4ca9-8a92-964ab80a374c')
    def test_list_shares_both_params(self):
        zone_name = dns_data_utils.rand_zone_name(name="testdomain")
        zone = self.adm_zones_client.create_zone(name=zone_name)[1]
        self.addCleanup(self.adm_zones_client.delete_zone,
                        zone['id'], delete_shares=True)
        shared_zone = self.adm_shr_client.create_zone_share(
            zone['id'], self.alt_zone_client.project_id)[1]
        self.addCleanup(self.adm_shr_client.delete_zone_share,
                        zone['id'], shared_zone['id'])

        shared_zone_demo = self.adm_shr_client.create_zone_share(
            zone['id'], self.demo_zone_client.project_id)[1]
        self.addCleanup(self.adm_shr_client.delete_zone_share,
                        zone['id'], shared_zone_demo['id'])

        LOG.info('List zone shares for zone and alt target project id')
        params = {"zone_id": zone['id'],
                  'target_project_id': self.demo_zone_client.project_id
                  }
        body = self.adm_shr_client.list_shares(params=params)[1]
        self.assertEqual(1, len(body['shared_zones']))

        LOG.info('List zone shares for zone and demo target project id')
        params = {"zone_id": zone['id'],
                  'target_project_id': self.alt_share_zone_client.project_id
                  }
        body = self.adm_shr_client.list_shares(params=params)[1]
        self.assertEqual(1, len(body['shared_zones']))

        LOG.info('List zone shares for zone_id param')
        params = {"zone_id": zone['id']}
        body = self.adm_shr_client.list_shares(params=params)[1]
        self.assertEqual(2, len(body['shared_zones']))
        targets = []
        for share in body['shared_zones']:
            targets.append(share['target_project_id'])
        self.assertIn(self.alt_zone_client.project_id, targets)
        self.assertIn(self.demo_zone_client.project_id, targets)


class NegativeSharedZonesTest(BaseSharedZoneTest):

    credentials = ['primary', 'admin', 'alt', ['demo']]

    @classmethod
    def setup_credentials(cls):
        # Do not create network resources for these test.
        cls.set_network_resources()
        super(NegativeSharedZonesTest, cls).setup_credentials()

    @decorators.idempotent_id('4389a12b-8609-493c-9640-d3c67b625022')
    def test_target_project_cannot_delete_zone(self):
        shared_zone = self.share_zone_client.create_zone_share(
            self.zone['id'], self.alt_zone_client.project_id)[1]
        self.addCleanup(self.share_zone_client.delete_zone_share,
                        self.zone['id'], shared_zone['id'],
                        ignore_errors=lib_exc.NotFound)

        LOG.info('Ensure target project cannot delete zone')
        with self.assertRaisesDns(lib_exc.NotFound, "zone_not_found", 404):
            self.alt_zone_client.delete_zone(self.zone['id'], delete_shares=True)

    @decorators.idempotent_id('f4354b5c-8dbb-4bb9-8025-f65f8f2b21fb')
    def test_target_project_cannot_update_zone(self):
        zone_name = dns_data_utils.rand_zone_name(name="testdomain")
        zone = self.zones_client.create_zone(name=zone_name)[1]
        self.addCleanup(self.zones_client.delete_zone,
                        self.zone['id'],
                        ignore_errors=lib_exc.NotFound,
                        delete_shares=True)
        shared_zone = self.share_zone_client.create_zone_share(
            zone['id'], self.alt_zone_client.project_id)[1]
        self.addCleanup(self.share_zone_client.delete_zone_share,
                        self.zone['id'], shared_zone['id'],
                        ignore_errors=lib_exc.NotFound,
                        )

        LOG.info('Ensure target project cannot update the zone')
        with self.assertRaisesDns(
                lib_exc.NotFound, 'zone_not_found', 404):
            self.alt_zone_client.update_zone(self.zone['id'], ttl=5)

    @decorators.idempotent_id('4389a12b-8609-493c-9640-d3c67b625022')
    def test_target_project_share_permissions(self):
        zone_name = dns_data_utils.rand_zone_name(name="testdomain")
        zone = self.zones_client.create_zone(name=zone_name)[1]
        self.addCleanup(self.zones_client.delete_zone,
                        self.zone['id'],
                        ignore_errors=lib_exc.NotFound,
                        delete_shares=True)
        shared_zone = self.share_zone_client.create_zone_share(
            zone['id'], self.alt_zone_client.project_id)[1]
        self.addCleanup(self.share_zone_client.delete_zone_share,
                        self.zone['id'], shared_zone['id'],
                        ignore_errors=lib_exc.NotFound)

        LOG.info('Ensure target project cannot share shared zone')
        self.assertRaises(
            lib_exc.NotFound,
            self.alt_share_zone_client.create_zone_share,
            self.zone['id'],
            self.demo_zone_client.project_id)

    @decorators.idempotent_id('957ba3f8-c250-11ed-a8b1-201e8823901f')
    def test_share_zone_with_yourself_is_not_allowed(self):
        with self.assertRaisesDns(lib_exc.BadRequest, 'bad_request', 400):
            self.share_zone_client.create_zone_share(
                zone_id=self.zone['id'],
                target_project_id=self.share_zone_client.project_id)


class AdminSharedZonesTest(BaseSharedZoneTest):

    @classmethod
    def setup_credentials(cls):
        # Do not create network resources for these test.
        cls.set_network_resources()
        super(AdminSharedZonesTest, cls).setup_credentials()

    @decorators.idempotent_id('2bb7bcb2-b824-11ed-9e56-201e8823901f')
    def test_create_zone_share_all_projects_header(self):
        LOG.info(
            'Admin user creates shared zone for Alt tenant '
            'using "x-auth-all-projects" header')
        headers = self.all_projects_header

        shared_zone = self.adm_shr_client.create_zone_share(
            self.zone['id'], self.alt_zone_client.project_id,
            headers=headers)[1]
        self.addCleanup(
            self.adm_shr_client.delete_zone_share, self.zone['id'],
            shared_zone['id'], headers=self.all_projects_header)
        self.assertTrue(uuidutils.is_uuid_like(shared_zone['id']))
        self.assertEqual(self.zone['id'], shared_zone['zone_id'])
        self.assertEqual(self.adm_shr_client.project_id,
                             shared_zone['project_id'])
        self.assertEqual(self.alt_zone_client.project_id,
                         shared_zone['target_project_id'])
        self.assertIsNotNone(shared_zone['created_at'])
        self.assertIsNone(shared_zone['updated_at'])
        self.assertIsNotNone(shared_zone['links'])

    @decorators.idempotent_id('f26cd3ac-b8fa-11ed-b4ca-201e8823901f')
    def test_create_zone_share_sudo_project_header(self):
        LOG.info(
            'Admin user creates shared zone for Alt tenant '
            'using "x-auth-sudo-project-id" header')
        sudo_header = {
            'x-auth-sudo-project-id': self.share_zone_client.project_id}
        shared_zone = self.adm_shr_client.create_zone_share(
            self.zone['id'], self.alt_zone_client.project_id,
            headers=sudo_header)[1]
        self.addCleanup(
            self.adm_shr_client.delete_zone_share, self.zone['id'],
            shared_zone['id'], headers=sudo_header)
        self.assertTrue(uuidutils.is_uuid_like(shared_zone['id']))
        self.assertEqual(self.zone['id'], shared_zone['zone_id'])
        self.assertEqual(self.share_zone_client.project_id,
                         shared_zone['project_id'])
        self.assertEqual(self.alt_zone_client.project_id,
                         shared_zone['target_project_id'])
        self.assertIsNotNone(shared_zone['created_at'])
        self.assertIsNone(shared_zone['updated_at'])
        self.assertIsNotNone(shared_zone['links'])

    @decorators.idempotent_id('ce2688e8-b90a-11ed-b4ca-201e8823901f')
    def test_show_shared_zone_all_projects_header(self):
        LOG.info(
            'Admin user creates shared zone for Alt tenant'
            ' using "x-auth-all-projects" header')
        # Scoped tokens do not have a project ID, work around that here
        headers = self.all_projects_header
        shared_zone = self.adm_shr_client.create_zone_share(
            self.zone['id'], self.alt_zone_client.project_id,
            headers=headers)[1]
        self.addCleanup(
            self.adm_shr_client.delete_zone_share, self.zone['id'],
            shared_zone['id'], headers=self.all_projects_header)

        LOG.info('Admin user shows shared zone and validates its content')
        body = self.adm_shr_client.show_zone_share(
            self.zone['id'], shared_zone['id'],
            headers=self.all_projects_header)[1]
        self.assertExpected(shared_zone, body, self.excluded_keys)

    @decorators.idempotent_id('46f7db22-b90c-11ed-b4ca-201e8823901f')
    def test_delete_zone_share_sudo_project_header(self):
        LOG.info(
            'Admin user creates shared zone for Alt tenant'
            ' using "x-auth-sudo-project-id" header')
        sudo_header = {
            'x-auth-sudo-project-id': self.share_zone_client.project_id}
        shared_zone = self.adm_shr_client.create_zone_share(
            self.zone['id'], self.alt_zone_client.project_id,
            headers=sudo_header)[1]
        self.addCleanup(
            self.adm_shr_client.delete_zone_share, self.zone['id'],
            shared_zone['id'], headers=sudo_header,
            ignore_errors=lib_exc.NotFound)

        LOG.info('As Admin delete zone share and ensure it was deleted')
        self.adm_shr_client.delete_zone_share(
            self.zone['id'], shared_zone['id'], headers=sudo_header)
        self.assertRaises(lib_exc.NotFound,
                          self.adm_shr_client.show_zone_share,
                          self.zone['id'], shared_zone['id'],
                          headers=sudo_header)


class AdminSharedZonesTestNegative(BaseSharedZoneTest):

    @classmethod
    def setup_credentials(cls):
        # Do not create network resources for these test.
        cls.set_network_resources()
        super(AdminSharedZonesTestNegative, cls).setup_credentials()

    @decorators.idempotent_id('595ae1fc-bce4-11ed-baf2-201e8823901f')
    def test_create_zone_share_invalid_project_id(self):
        LOG.info(
            'Admin user tries to create shared zone, using non existing '
            'project ID id in "x-auth-sudo-project-id" header')
        sudo_header = {
            'x-auth-sudo-project-id': data_utils.rand_uuid()}
        self.assertRaises(
            lib_exc.NotFound, self.adm_shr_client.create_zone_share,
            self.zone['id'], self.alt_zone_client.project_id,
            headers=sudo_header)

    @decorators.idempotent_id('aa42d82e-bcf6-11ed-baf2-201e8823901f')
    def test_create_zone_share_invalid_zone_id(self):
        LOG.info(
            'Admin user tries to create shared zone, using non existing '
            'zone ID and "x-auth-sudo-project-id" header')
        sudo_header = {
            'x-auth-sudo-project-id': self.alt_zone_client.project_id}
        self.assertRaises(
            lib_exc.NotFound, self.adm_shr_client.create_zone_share,
            data_utils.rand_uuid(), self.alt_zone_client.project_id,
            headers=sudo_header)

    @decorators.idempotent_id('9e7202ba-bd94-11ed-80f5-201e8823901f')
    def test_show_shared_zone_invalid_shared_zone_id(self):
        LOG.info('Admin tries to show shared zone using not '
                 'existing shared zone ID')
        sudo_header = {
            'x-auth-sudo-project-id': self.alt_zone_client.project_id}
        self.assertRaises(
            lib_exc.NotFound, self.adm_shr_client.show_zone_share,
            self.zone['id'], data_utils.rand_uuid(), headers=sudo_header)

    @decorators.idempotent_id('8852329c-bd95-11ed-80f5-201e8823901f')
    def test_show_shared_zone_invalid_project_id(self):
        LOG.info('Admin tries to show shared zone '
                 'using not existing project ID')
        sudo_header = {
            'x-auth-sudo-project-id': self.share_zone_client.project_id}
        shared_zone = self.adm_shr_client.create_zone_share(
            self.zone['id'], self.alt_zone_client.project_id,
            headers=sudo_header)[1]
        self.addCleanup(
            self.adm_shr_client.delete_zone_share, self.zone['id'],
            shared_zone['id'], headers=sudo_header)
        sudo_header_invalid_project_id = {
            'x-auth-sudo-project-id': data_utils.rand_uuid()}
        self.assertRaises(
            lib_exc.NotFound, self.adm_shr_client.show_zone_share,
            self.zone['id'], shared_zone['id'],
            headers=sudo_header_invalid_project_id)

    @decorators.idempotent_id('871e7e1c-bd9a-11ed-80f5-201e8823901f')
    @decorators.skip_because(bug="2009819")
    def test_list_shares_invalid_zone_id(self):
        LOG.info('Admin user tries to list shared zone '
                 'using not existing zone ID')
        sudo_header = {
            'x-auth-sudo-project-id': self.share_zone_client.project_id}
        self.assertRaises(
            lib_exc.NotFound, self.adm_shr_client.list_shares,
            data_utils.rand_uuid(), headers=sudo_header)

    @decorators.idempotent_id('e71068c8-bdb1-11ed-80f5-201e8823901f')
    @ decorators.skip_because(bug="2009819")
    def test_list_shares_invalid_project_id(self):
        LOG.info('Admin user tries to list shared zone using '
                 'not existing project ID')
        sudo_header = {
            'x-auth-sudo-project-id': data_utils.rand_uuid()}
        self.assertRaises(
            lib_exc.NotFound, self.adm_shr_client.list_shares,
            self.zone['id'], headers=sudo_header)

    @decorators.idempotent_id('7136b430-bdb2-11ed-80f5-201e8823901f')
    def test_delete_zone_share_invalid_project_id(self):
        LOG.info('Admin user creates shared zone for Alt user')
        sudo_header = {
            'x-auth-sudo-project-id': self.share_zone_client.project_id}
        shared_zone = self.adm_shr_client.create_zone_share(
            self.zone['id'], self.alt_zone_client.project_id,
            headers=sudo_header)[1]
        self.addCleanup(
            self.adm_shr_client.delete_zone_share, self.zone['id'],
            shared_zone['id'], headers=sudo_header,
            ignore_errors=lib_exc.NotFound)
        LOG.info('Admin user tries to delete the shared zone '
                 'using non existing project ID')
        invalid_sudo_header = {
            'x-auth-sudo-project-id': data_utils.rand_uuid()}
        self.assertRaises(
            lib_exc.NotFound, self.adm_shr_client.delete_zone_share,
            self.zone['id'], shared_zone['id'],
            headers=invalid_sudo_header)

    @decorators.idempotent_id('d44c65e2-bdc1-11ed-80f5-201e8823901f')
    def test_delete_zone_share_invalid_shared_zone_id(self):
        LOG.info('Admin user creates shared zone for Alt user')
        sudo_header = {
            'x-auth-sudo-project-id': self.share_zone_client.project_id}
        shared_zone = self.adm_shr_client.create_zone_share(
            self.zone['id'], self.alt_zone_client.project_id,
            headers=sudo_header)[1]
        self.addCleanup(
            self.adm_shr_client.delete_zone_share, self.zone['id'],
            shared_zone['id'], headers=sudo_header,
            ignore_errors=lib_exc.NotFound)
        LOG.info('Admin user tries to delete the shared zone '
                 'using non existing shared zone ID')
        self.assertRaises(
            lib_exc.NotFound, self.adm_shr_client.delete_zone_share,
            self.zone['id'], data_utils.rand_uuid(),
            headers=sudo_header)

    @decorators.idempotent_id('06de2342-bdc2-11ed-80f5-201e8823901f')
    def test_delete_zone_share_invalid_zone_id(self):
        LOG.info('Admin user creates shared zone for Alt user')
        sudo_header = {
            'x-auth-sudo-project-id': self.share_zone_client.project_id}
        shared_zone = self.adm_shr_client.create_zone_share(
            self.zone['id'], self.alt_zone_client.project_id,
            headers=sudo_header)[1]
        self.addCleanup(
            self.adm_shr_client.delete_zone_share, self.zone['id'],
            shared_zone['id'], headers=sudo_header,
            ignore_errors=lib_exc.NotFound)
        LOG.info('Admin user tries to delete the shared zone '
                 'using non zone ID')
        self.assertRaises(
            lib_exc.NotFound, self.adm_shr_client.delete_zone_share,
            data_utils.rand_uuid(), shared_zone['id'],
            headers=sudo_header)
