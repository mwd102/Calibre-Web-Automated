"""Custom DNS64 cover egress preserves Advocate's embedded IPv4 checks."""

import ipaddress
import socket

from cps.cw_advocate.addrvalidator import AddrValidator


def _record(address):
    return socket.AF_INET6, socket.SOCK_STREAM, socket.IPPROTO_TCP, "", (address, 443, 0, 0)


def test_custom_dns64_prefix_allows_embedded_public_ipv4():
    prefix = ipaddress.ip_network("64:ff9b:1::/96")
    validator = AddrValidator(allow_ipv6=True, allow_dns64=True,
                              dns64_prefixes={prefix}, autodetect_local_addresses=False)
    assert validator.is_addrinfo_allowed(_record("64:ff9b:1::808:808"))


def test_custom_dns64_prefix_rejects_embedded_private_ipv4():
    prefix = ipaddress.ip_network("64:ff9b:1::/96")
    validator = AddrValidator(allow_ipv6=True, allow_dns64=True,
                              dns64_prefixes={prefix}, autodetect_local_addresses=False)
    assert not validator.is_addrinfo_allowed(_record("64:ff9b:1::7f00:1"))
    assert not validator.is_addrinfo_allowed(_record("64:ff9b:1::a00:1"))
