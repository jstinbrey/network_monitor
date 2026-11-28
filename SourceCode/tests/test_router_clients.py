"""The FiberHome client table stays separate from local discovery and stored results."""
import pytest

from netmonitor import config, models, services
from netmonitor.core import router_clients

COPIED = ("ID\tSSID\tMAC\tIP\n"
          "1\tMain 5 GHz\t02:00:00:00:00:01\t192.168.1.2\n"
          "2\tMain 2.4 GHz\t02-00-00-00-00-02\t192.168.1.3\n"
          "3\nMain 5 GHz\n02:00:00:00:00:03\n--")


def test_read_fiberhome_rows_with_or_without_an_ipv4_address():
    assert router_clients.read_table(COPIED) == (
        router_clients.Client("02-00-00-00-00-01", "Main 5 GHz", "192.168.1.2"),
        router_clients.Client("02-00-00-00-00-02", "Main 2.4 GHz", "192.168.1.3"),
        router_clients.Client("02-00-00-00-00-03", "Main 5 GHz", None),
    )
    with pytest.raises(ValueError, match="No client rows"):
        router_clients.read_table("ID SSID MAC IP")


def test_map_adds_router_only_clients_and_drops_overlay_on_another_network(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "test.db")
    phone = models.Device("192.168.1.2", "02:00:00:00:00:01", "Phone", replied_icmp=True)
    info = models.NetworkInfo("pc", "192.168.1.4", "255.255.255.0", "192.168.1.0/24",
                              "192.168.1.1", "192.168.1.254", "192.168.1.1", 254)
    snapshot = router_clients.Snapshot("home", "2026-11-28T15:00", router_clients.read_table(COPIED))
    monkeypatch.setattr(services, "_live", lambda: (info, {}, "home", [phone]))
    devices, stats, _ = services.map_data(router_snapshot=snapshot)
    assert [d.ip for d in devices] == ["192.168.1.2", "192.168.1.3"]
    assert devices[0].router_ssid == "Main 5 GHz" and not devices[0].router_only
    assert devices[1].router_only and stats[devices[1].ip].status == models.NO_DATA
    monkeypatch.setattr(services, "_live", lambda: (info, {}, "guest", [phone]))
    assert services.map_data(router_snapshot=snapshot)[0] == [phone]
