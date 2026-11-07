import socket
import unittest
from unittest.mock import AsyncMock, patch

from reolink_aio.api import Host
from reolink_aio.baichuan.baichuan import Baichuan
from reolink_aio.baichuan.udp_protocol import BaichuanUdpConnection
from reolink_aio.enums import ConnectionEnum
from reolink_aio.exceptions import ReolinkConnectionError

TEST_HOST = "127.0.0.1"


def _free_udp_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


class TestUdpLocalPort(unittest.IsolatedAsyncioTestCase):
    async def test_default_is_random_local_port(self) -> None:
        baichuan = Baichuan(
            host=TEST_HOST,
            username="user",
            password="pass",
            http_api=AsyncMock(uid="UNKNOWN"),
            connection_type=ConnectionEnum.udp,
        )
        self.assertEqual(baichuan.udp_local_port, 0)

        with patch.object(BaichuanUdpConnection, "connect", AsyncMock()):
            await baichuan._connect_if_needed()
        self.assertTrue(baichuan._connection._random_local_port)  # type: ignore[union-attr]

    async def test_fixed_port_is_used_for_udp_connection(self) -> None:
        port = _free_udp_port()
        baichuan = Baichuan(
            host=TEST_HOST,
            username="user",
            password="pass",
            http_api=AsyncMock(uid="UNKNOWN"),
            connection_type=ConnectionEnum.udp,
            udp_local_port=port,
        )

        with patch.object(BaichuanUdpConnection, "connect", AsyncMock()):
            await baichuan._connect_if_needed()
        connection = baichuan._connection
        self.assertIsInstance(connection, BaichuanUdpConnection)
        self.assertFalse(connection._random_local_port)  # type: ignore[union-attr]
        self.assertEqual(connection._local_port, port)  # type: ignore[union-attr]

    async def test_fixed_port_is_used_when_connection_type_is_searched(self) -> None:
        port = _free_udp_port()
        baichuan = Baichuan(
            host=TEST_HOST,
            username="user",
            password="pass",
            http_api=AsyncMock(uid="UNKNOWN"),
            udp_local_port=port,
        )

        with patch("reolink_aio.baichuan.baichuan.BaichuanUdpConnection") as udp_class, patch("reolink_aio.baichuan.baichuan.BaichuanTcpConnection") as tcp_class:
            udp_class.return_value.connect = AsyncMock(side_effect=ReolinkConnectionError("no udp"))
            udp_class.return_value.drop_connection = AsyncMock()
            tcp_class.return_value.connect = AsyncMock(side_effect=ReolinkConnectionError("no tcp"))
            tcp_class.return_value.drop_connection = AsyncMock()
            with self.assertRaises(ReolinkConnectionError):
                await baichuan._connect_find_type()

        self.assertEqual(udp_class.call_args.args[1], port)

    async def test_fixed_port_is_bound_by_udp_socket(self) -> None:
        port = _free_udp_port()
        connection = BaichuanUdpConnection(TEST_HOST, port)
        transport, _protocol = await connection._create_connection()
        try:
            self.assertEqual(transport.get_extra_info("sockname")[1], port)
        finally:
            transport.close()
            _protocol.drop_coroutine.close()

    def test_port_out_of_range_is_rejected(self) -> None:
        for port in (-1, 65536):
            with self.subTest(port=port), self.assertRaises(ValueError):
                Baichuan(
                    host=TEST_HOST,
                    username="user",
                    password="pass",
                    http_api=AsyncMock(),
                    udp_local_port=port,
                )

    async def test_host_passes_udp_local_port_to_baichuan(self) -> None:
        host = Host(TEST_HOST, "admin", "pass", bc_udp_local_port=44230)
        try:
            self.assertEqual(host.baichuan.udp_local_port, 44230)
        finally:
            await host._aiohttp_session.close()


if __name__ == "__main__":
    unittest.main()
