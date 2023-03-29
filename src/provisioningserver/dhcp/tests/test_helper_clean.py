# Copyright 2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for maas-dhcp-support clean command."""


from maastesting import dev_root
from maastesting.testcase import MAASTestCase
from provisioningserver.utils.fs import read_text_file
from provisioningserver.utils.shell import call_and_check

LEASES_FILE_WITH_HOSTS = """\
lease 192.168.10.67 {
  starts 2 2016/03/22 13:44:15;
  ends 3 2016/03/23 01:44:15;
  cltt 2 2016/03/22 13:44:15;
  binding state active;
  next binding state free;
  rewind binding state free;
  hardware ethernet 74:d4:35:89:bc:f2;
  set clht = "zoochemical-carlton";
  set cllt = "43200";
  set clip = "192.168.10.67";
  set clhw = "74:d4:35:89:bc:f2";
  set vendor-class-identifier = "Linux ipconfig";
  client-hostname "zoochemical-carlton";
}
host 74-d4-35-89-b9-e8 {
  dynamic;
  hardware ethernet 74:d4:35:89:b9:e8;
  fixed-address 192.168.10.5;
}
lease 192.168.10.69 {
  starts 2 2016/03/22 13:44:15;
  ends 3 2016/03/23 01:44:15;
  cltt 2 2016/03/22 13:44:15;
  binding state active;
  next binding state free;
  rewind binding state free;
  hardware ethernet 74:d4:35:89:bd:25;
  set clht = "undetesting-johnetta";
  set cllt = "43200";
  set clip = "192.168.10.69";
  set clhw = "74:d4:35:89:bd:25";
  set vendor-class-identifier = "Linux ipconfig";
}
host 74-d4-35-89-bc-26 {
  dynamic;
  hardware ethernet 74:d4:35:89:bc:26;
  fixed-address 192.168.10.7;
}
host 74-d4-35-89-bc-23 {
  dynamic;
  deleted;
}
"""


LEASES_FILE_WITHOUT_HOSTS = """\
lease 192.168.10.67 {
  starts 2 2016/03/22 13:44:15;
  ends 3 2016/03/23 01:44:15;
  cltt 2 2016/03/22 13:44:15;
  binding state active;
  next binding state free;
  rewind binding state free;
  hardware ethernet 74:d4:35:89:bc:f2;
  set clht = "zoochemical-carlton";
  set cllt = "43200";
  set clip = "192.168.10.67";
  set clhw = "74:d4:35:89:bc:f2";
  set vendor-class-identifier = "Linux ipconfig";
  client-hostname "zoochemical-carlton";
}
lease 192.168.10.69 {
  starts 2 2016/03/22 13:44:15;
  ends 3 2016/03/23 01:44:15;
  cltt 2 2016/03/22 13:44:15;
  binding state active;
  next binding state free;
  rewind binding state free;
  hardware ethernet 74:d4:35:89:bd:25;
  set clht = "undetesting-johnetta";
  set cllt = "43200";
  set clip = "192.168.10.69";
  set clhw = "74:d4:35:89:bd:25";
  set vendor-class-identifier = "Linux ipconfig";
}
"""


class TestDHCPClean(MAASTestCase):
    def test_removes_hosts_from_leases_file(self):
        path = self.make_file(contents=LEASES_FILE_WITH_HOSTS)
        call_and_check(
            [
                f"{dev_root}/package-files/usr/sbin/maas-dhcp-helper",
                "clean",
                path,
            ]
        )
        self.assertEqual(LEASES_FILE_WITHOUT_HOSTS, read_text_file(path))
