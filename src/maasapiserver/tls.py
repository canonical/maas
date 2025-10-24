# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

# ruff: noqa
# pyright: basic, reportArgumentType=false

import asyncio
import ssl
from urllib.parse import unquote

from cryptography import x509
from cryptography.hazmat.backends import default_backend
import h11
from uvicorn.protocols.http.flow_control import (
    HIGH_WATER_LIMIT,
    service_unavailable,
)
from uvicorn.protocols.http.h11_impl import H11Protocol, RequestResponseCycle


class TLSPatchedH11Protocol(H11Protocol):
    """
    Patched version of H11Protocol to include the information about TSL. We can get rid of this when Uvicorn will officially
    add support for it https://github.com/Kludex/uvicorn/issues/1118 .
    """

    def _include_tls(self, transport, scope):
        scope["extensions"] = {}

        ssl_object = transport.get_extra_info("ssl_object")

        if ssl_object:
            tlsext = scope["extensions"]["tls"] = {
                "tls_used": True,
                "client_cert_chain": [],
                "tls_version": {
                    "TLSv1": 0x0301,
                    "TLSv1.1": 0x0302,
                    "TLSv1.2": 0x0303,
                    "TLSv1.3": 0x0304,
                }.get(ssl_object.version(), None),
            }

            client_cert = ssl_object.getpeercert(binary_form=True)
            if client_cert:
                pem_cert = ssl.DER_cert_to_PEM_cert(client_cert)
                tlsext["client_cert_chain"].append(pem_cert)

                # Extract CN using cryptography
                cert_obj = x509.load_pem_x509_certificate(
                    pem_cert.encode("utf-8"), default_backend()
                )
                cn_attr = cert_obj.subject.get_attributes_for_oid(
                    x509.NameOID.COMMON_NAME
                )
                if cn_attr:
                    tlsext["client_cn"] = cn_attr[0].value

    # Copyright © 2017-present, Encode OSS Ltd. All rights reserved.
    # Redistribution and use in source and binary forms, with or without modification, are permitted provided that the following conditions are met:
    #   - Redistributions of source code must retain the above copyright notice, this list of conditions and the following disclaimer.
    #   - Redistributions in binary form must reproduce the above copyright notice, this list of conditions and the following disclaimer in the documentation and/or other materials provided with the distribution.
    #   - Neither the name of the copyright holder nor the names of its contributors may be used to endorse or promote products derived from this software without specific prior written permission.
    # THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
    def handle_events(self) -> None:
        while True:
            try:
                event = self.conn.next_event()
            except h11.RemoteProtocolError:
                msg = "Invalid HTTP request received."
                self.logger.warning(msg)
                self.send_400_response(msg)
                return

            if event is h11.NEED_DATA:
                break

            elif event is h11.PAUSED:
                # This case can occur in HTTP pipelining, so we need to
                # stop reading any more data, and ensure that at the end
                # of the active request/response cycle we handle any
                # events that have been buffered up.
                self.flow.pause_reading()
                break

            elif isinstance(event, h11.Request):
                self.headers = [
                    (key.lower(), value) for key, value in event.headers
                ]
                raw_path, _, query_string = event.target.partition(b"?")
                path = unquote(raw_path.decode("ascii"))
                full_path = self.root_path + path
                full_raw_path = self.root_path.encode("ascii") + raw_path
                self.scope = {
                    "type": "http",
                    "asgi": {
                        "version": self.config.asgi_version,
                        "spec_version": "2.3",
                    },
                    "http_version": event.http_version.decode("ascii"),
                    "server": self.server,
                    "client": self.client,
                    "scheme": self.scheme,  # type: ignore[typeddict-item]
                    "method": event.method.decode("ascii"),
                    "root_path": self.root_path,
                    "path": full_path,
                    "raw_path": full_raw_path,
                    "query_string": query_string,
                    "headers": self.headers,
                    "state": self.app_state.copy(),
                }
                ### BEGIN PATCH
                self._include_tls(self.transport, self.scope)
                ### END PATCH

                upgrade = self._get_upgrade()
                if upgrade == b"websocket" and self._should_upgrade_to_ws():
                    self.handle_websocket_upgrade(event)
                    return

                # Handle 503 responses when 'limit_concurrency' is exceeded.
                if self.limit_concurrency is not None and (
                    len(self.connections) >= self.limit_concurrency
                    or len(self.tasks) >= self.limit_concurrency
                ):
                    app = service_unavailable
                    message = "Exceeded concurrency limit."
                    self.logger.warning(message)
                else:
                    app = self.app

                # When starting to process a request, disable the keep-alive
                # timeout. Normally we disable this when receiving data from
                # client and set back when finishing processing its request.
                # However, for pipelined requests processing finishes after
                # already receiving the next request and thus the timer may
                # be set here, which we don't want.
                self._unset_keepalive_if_required()

                self.cycle = RequestResponseCycle(
                    scope=self.scope,
                    conn=self.conn,
                    transport=self.transport,
                    flow=self.flow,
                    logger=self.logger,
                    access_logger=self.access_logger,
                    access_log=self.access_log,
                    default_headers=self.server_state.default_headers,
                    message_event=asyncio.Event(),
                    on_response=self.on_response_complete,
                )
                task = self.loop.create_task(self.cycle.run_asgi(app))
                task.add_done_callback(self.tasks.discard)
                self.tasks.add(task)

            elif isinstance(event, h11.Data):
                if self.conn.our_state is h11.DONE:
                    continue
                self.cycle.body += event.data
                if len(self.cycle.body) > HIGH_WATER_LIMIT:
                    self.flow.pause_reading()
                self.cycle.message_event.set()

            elif isinstance(event, h11.EndOfMessage):
                if self.conn.our_state is h11.DONE:
                    self.transport.resume_reading()
                    self.conn.start_next_cycle()
                    continue
                self.cycle.more_body = False
                self.cycle.message_event.set()
