# Copyright 2014-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Test AMP argument classes."""

from twisted.protocols import amp

from maastesting.factory import factory
from provisioningserver.rpc import arguments


class TestCompressedAmpList:
    def test_round_trip(self):
        argument = arguments.CompressedAmpList([("thing", amp.Unicode())])
        arg_name = factory.make_name()
        b_arg_name = arg_name.encode()
        example = {arg_name: [{"thing": factory.make_name("thing")}]}

        box: dict[bytes, bytes] = {}
        argument.toBox(b_arg_name, box, example.copy(), None)
        assert isinstance(box[b_arg_name], bytes)

        decoded: dict[bytes, bytes] = {}
        argument.fromBox(b_arg_name, box, decoded, None)
        assert example == decoded

    def test_compression_is_worth_it(self):
        arg_name = "leases"
        b_arg_name = arg_name.encode()
        argument = arguments.CompressedAmpList(
            [("ip", amp.Unicode()), ("mac", amp.Unicode())]
        )
        leases = {
            arg_name: [
                {
                    "ip": factory.make_ipv4_address(),
                    "mac": factory.make_mac_address(),
                }
                for _ in range(10000)
            ]
        }

        box: dict[bytes, bytes] = {}
        argument.toBox(b_arg_name, box, leases, None)
        assert len(box.keys()) == 3
        for v in box.items():
            assert len(v) < 2**16
