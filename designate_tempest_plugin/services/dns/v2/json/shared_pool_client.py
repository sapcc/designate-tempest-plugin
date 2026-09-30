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

from designate_tempest_plugin.services.dns.v2.json import base


class SharedPoolClient(base.DnsClientV2Base):
    """API V2 Tempest REST client for Shared Pool API"""

    @base.handle_errors
    def create_pool_share(self, pool_id, target_domain_id,
                          params=None):
        """Share a pool with a target domain.

        :param pool_id: UUID of the pool to share.
        :param target_domain_id: The Keystone domain ID to share with.
        :param params: Query parameters to include in the request URI.
        :return: A tuple with the server response and the created share.
        """
        body = {'target_domain_id': target_domain_id}
        resp, body = self._create_request(
            'pools/{}/shares'.format(pool_id),
            data=body,
            params=params,
        )
        self.expected_success(201, resp.status)
        return resp, body

    @base.handle_errors
    def show_pool_share(self, pool_id, pool_share_id, params=None):
        """Get a specific pool share.

        :param pool_id: UUID of the pool.
        :param pool_share_id: UUID of the share.
        :param params: Query parameters to include in the request URI.
        :return: A tuple with the server response and the share body.
        """
        return self._show_request(
            'pools/{}/shares'.format(pool_id),
            pool_share_id,
            params=params,
        )

    @base.handle_errors
    def list_pool_shares(self, pool_id, params=None):
        """List all shares for a pool.

        :param pool_id: UUID of the pool.
        :param params: Query parameters to include in the request URI.
        :return: A tuple with the server response and the list of shares.
        """
        return self._list_request(
            'pools/{}/shares'.format(pool_id),
            params=params,
        )

    @base.handle_errors
    def delete_pool_share(self, pool_id, pool_share_id, params=None):
        """Delete a pool share.

        :param pool_id: UUID of the pool.
        :param pool_share_id: UUID of the share.
        :param params: Query parameters to include in the request URI.
        :return: A tuple with the server response and the response body.
        """
        resp, body = self._delete_request(
            'pools/{}/shares'.format(pool_id),
            pool_share_id,
            params=params,
        )
        self.expected_success(204, resp.status)
        return resp, body
