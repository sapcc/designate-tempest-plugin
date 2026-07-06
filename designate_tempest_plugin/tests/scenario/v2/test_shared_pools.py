# Copyright 2026 Cloudification GmbH. All rights reserved.
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
from oslo_utils import versionutils
from tempest import config
from tempest.lib import decorators
from tempest.lib import exceptions as lib_exc
from tempest.lib.common.utils import data_utils

from designate_tempest_plugin import data_utils as dns_data_utils
from designate_tempest_plugin.tests import base

CONF = config.CONF
LOG = logging.getLogger(__name__)


class SharedPoolsTest(base.BaseDnsV2Test):
    credentials = ['admin', 'primary']

    @classmethod
    def setup_clients(cls):
        super(SharedPoolsTest, cls).setup_clients()
        cls.admin_tld_client = cls.os_admin.dns_v2.TldClient()
        cls.admin_pool_client = cls.os_admin.dns_v2.PoolClient()
        cls.admin_shared_pool_client = (
            cls.os_admin.dns_v2.SharedPoolClient())

    @classmethod
    def resource_setup(cls):
        super(SharedPoolsTest, cls).resource_setup()

        if not versionutils.is_compatible('2.3', cls.api_version,
                                          same_major=False):
            raise cls.skipException(
                'The shared pools tests require Designate API '
                'version 2.3 or newer. Skipping.')

        tld_name = dns_data_utils.rand_zone_name(name='SharedPoolsTest')
        cls.tld_name = f'.{tld_name}'
        cls.class_tld = cls.admin_tld_client.create_tld(
            tld_name=tld_name[:-1])

        # Create a Keystone domain for domain-based tests
        cls.test_domain = cls.os_admin.identity_v3.DomainsClient(
        ).create_domain(
            name=data_utils.rand_name('shared-pool-test-domain'),
            description='Temp domain for shared pool tests',
        )['domain']

        # Create a pool owned by the test domain
        cls.test_pool = cls.admin_pool_client.create_pool(
            pool_name=data_utils.rand_name('shared-pool-test'),
        )[1]
        # Set domain_id on the pool via direct API (requires admin)
        # The pool is created without domain_id - used for share tests

    @classmethod
    def _delete_domain(cls, domain_id):
        domains_client = cls.os_admin.identity_v3.DomainsClient()
        domains_client.update_domain(domain_id, enabled=False)
        domains_client.delete_domain(domain_id)

    @classmethod
    def resource_cleanup(cls):
        cls.admin_pool_client.delete_pool(cls.test_pool['id'])
        cls._delete_domain(cls.test_domain['id'])
        cls.admin_tld_client.delete_tld(cls.class_tld[1]['id'])
        super(SharedPoolsTest, cls).resource_cleanup()

    @decorators.idempotent_id('a1b2c3d4-0001-4000-8000-000000000001')
    def test_create_pool_share(self):
        LOG.info('Share pool %s with domain %s',
                 self.test_pool['id'], self.test_domain['id'])

        share = self.admin_shared_pool_client.create_pool_share(
            self.test_pool['id'],
            target_domain_id=self.test_domain['id'],
        )[1]
        self.addCleanup(
            self.admin_shared_pool_client.delete_pool_share,
            self.test_pool['id'], share['id'])

        self.assertEqual(self.test_pool['id'], share['pool_id'])
        self.assertEqual(self.test_domain['id'], share['target_domain_id'])
        self.assertIn('id', share)
        self.assertIn('created_at', share)
        self.assertIsNone(share['updated_at'])
        self.assertIn('self', share['links'])
        self.assertIn('pool', share['links'])
        self.assertNotIn('zone', share['links'])

    @decorators.idempotent_id('a1b2c3d4-0001-4000-8000-000000000002')
    def test_show_pool_share(self):
        share = self.admin_shared_pool_client.create_pool_share(
            self.test_pool['id'],
            target_domain_id=self.test_domain['id'],
        )[1]
        self.addCleanup(
            self.admin_shared_pool_client.delete_pool_share,
            self.test_pool['id'], share['id'])

        LOG.info('Show pool share %s', share['id'])
        shown = self.admin_shared_pool_client.show_pool_share(
            self.test_pool['id'], share['id'])[1]

        self.assertEqual(share['id'], shown['id'])
        self.assertEqual(share['pool_id'], shown['pool_id'])
        self.assertEqual(share['target_domain_id'], shown['target_domain_id'])

    @decorators.idempotent_id('a1b2c3d4-0001-4000-8000-000000000003')
    def test_list_pool_shares(self):
        LOG.info('List shares for pool %s before creating any',
                 self.test_pool['id'])
        shares_before = self.admin_shared_pool_client.list_pool_shares(
            self.test_pool['id'])[1]['shared_pools']

        share = self.admin_shared_pool_client.create_pool_share(
            self.test_pool['id'],
            target_domain_id=self.test_domain['id'],
        )[1]
        self.addCleanup(
            self.admin_shared_pool_client.delete_pool_share,
            self.test_pool['id'], share['id'])

        shares_after = self.admin_shared_pool_client.list_pool_shares(
            self.test_pool['id'])[1]['shared_pools']

        self.assertEqual(len(shares_before) + 1, len(shares_after))
        share_ids = [s['id'] for s in shares_after]
        self.assertIn(share['id'], share_ids)

    @decorators.idempotent_id('a1b2c3d4-0001-4000-8000-000000000004')
    def test_delete_pool_share(self):
        share = self.admin_shared_pool_client.create_pool_share(
            self.test_pool['id'],
            target_domain_id=self.test_domain['id'],
        )[1]

        LOG.info('Delete pool share %s', share['id'])
        self.admin_shared_pool_client.delete_pool_share(
            self.test_pool['id'], share['id'])

        LOG.info('Verify share no longer exists')
        self.assertRaises(
            lib_exc.NotFound,
            self.admin_shared_pool_client.show_pool_share,
            self.test_pool['id'], share['id'],
        )

    @decorators.idempotent_id('a1b2c3d4-0001-4000-8000-000000000005')
    def test_create_duplicate_pool_share_returns_409(self):
        share = self.admin_shared_pool_client.create_pool_share(
            self.test_pool['id'],
            target_domain_id=self.test_domain['id'],
        )[1]
        self.addCleanup(
            self.admin_shared_pool_client.delete_pool_share,
            self.test_pool['id'], share['id'])

        LOG.info('Attempt to create duplicate share')
        self.assertRaises(
            lib_exc.Conflict,
            self.admin_shared_pool_client.create_pool_share,
            self.test_pool['id'],
            target_domain_id=self.test_domain['id'],
        )

    @decorators.idempotent_id('a1b2c3d4-0001-4000-8000-000000000006')
    def test_show_nonexistent_pool_share_returns_404(self):
        self.assertRaises(
            lib_exc.NotFound,
            self.admin_shared_pool_client.show_pool_share,
            self.test_pool['id'],
            'ffffffff-ffff-ffff-ffff-ffffffffffff',
        )

    @decorators.idempotent_id('a1b2c3d4-0001-4000-8000-000000000007')
    def test_delete_nonexistent_pool_share_returns_404(self):
        self.assertRaises(
            lib_exc.NotFound,
            self.admin_shared_pool_client.delete_pool_share,
            self.test_pool['id'],
            'ffffffff-ffff-ffff-ffff-ffffffffffff',
        )

    @decorators.attr(type='slow')
    @decorators.idempotent_id('a1b2c3d4-0001-4000-8000-000000000008')
    def test_pool_shared_field_reflects_share_status(self):
        """shared field on pool is False before share, True after."""
        pool = self.admin_pool_client.show_pool(self.test_pool['id'])[1]
        self.assertFalse(pool['shared'])

        share = self.admin_shared_pool_client.create_pool_share(
            self.test_pool['id'],
            target_domain_id=self.test_domain['id'],
        )[1]
        self.addCleanup(
            self.admin_shared_pool_client.delete_pool_share,
            self.test_pool['id'], share['id'])

        pool = self.admin_pool_client.show_pool(self.test_pool['id'])[1]
        self.assertTrue(pool['shared'])

    @decorators.attr(type='slow')
    @decorators.idempotent_id('a1b2c3d4-0001-4000-8000-000000000009')
    def test_list_pool_shares_filter_by_target_domain(self):
        domains_client = self.os_admin.identity_v3.DomainsClient()
        second_domain = domains_client.create_domain(
            name=data_utils.rand_name('shared-pool-filter-domain'),
        )['domain']
        self.addCleanup(self._delete_domain, second_domain['id'])

        share1 = self.admin_shared_pool_client.create_pool_share(
            self.test_pool['id'],
            target_domain_id=self.test_domain['id'],
        )[1]
        self.addCleanup(
            self.admin_shared_pool_client.delete_pool_share,
            self.test_pool['id'], share1['id'])

        share2 = self.admin_shared_pool_client.create_pool_share(
            self.test_pool['id'],
            target_domain_id=second_domain['id'],
        )[1]
        self.addCleanup(
            self.admin_shared_pool_client.delete_pool_share,
            self.test_pool['id'], share2['id'])

        filtered = self.admin_shared_pool_client.list_pool_shares(
            self.test_pool['id'],
            params={'target_domain_id': self.test_domain['id']},
        )[1]['shared_pools']

        self.assertEqual(1, len(filtered))
        self.assertEqual(self.test_domain['id'],
                         filtered[0]['target_domain_id'])
