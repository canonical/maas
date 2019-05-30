/* Copyright 2015 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 *
 * Unit tests for nodesFilter.
 */

describe("nodesFilter", function() {
  // Load the MAAS module.
  beforeEach(angular.mock.module("MAAS"));

  // Load the nodesFilter.
  var nodesFilter;
  beforeEach(inject(function($filter) {
    nodesFilter = $filter("nodesFilter");
  }));

  it("matches using standard filter", function() {
    var matchingNode = {
      hostname: "name"
    };
    var otherNode = {
      hostname: "other"
    };
    var nodes = [matchingNode, otherNode];
    expect(nodesFilter(nodes, "nam")).toEqual([matchingNode]);
  });

  it("matches selected", function() {
    var matchingNode = {
      $selected: true
    };
    var otherNode = {
      $selected: false
    };
    var nodes = [matchingNode, otherNode];
    expect(nodesFilter(nodes, "in:selected")).toEqual([matchingNode]);
  });

  it("matches selected uppercase", function() {
    var matchingNode = {
      $selected: true
    };
    var otherNode = {
      $selected: false
    };
    var nodes = [matchingNode, otherNode];
    expect(nodesFilter(nodes, "in:Selected")).toEqual([matchingNode]);
  });

  it("matches selected uppercase in brackets", function() {
    var matchingNode = {
      $selected: true
    };
    var otherNode = {
      $selected: false
    };
    var nodes = [matchingNode, otherNode];
    expect(nodesFilter(nodes, "in:(Selected)")).toEqual([matchingNode]);
  });

  it("matches non-selected", function() {
    var matchingNode = {
      $selected: false
    };
    var otherNode = {
      $selected: true
    };
    var nodes = [matchingNode, otherNode];
    expect(nodesFilter(nodes, "in:!selected")).toEqual([matchingNode]);
  });

  it("matches non-selected uppercase", function() {
    var matchingNode = {
      $selected: false
    };
    var otherNode = {
      $selected: true
    };
    var nodes = [matchingNode, otherNode];
    expect(nodesFilter(nodes, "in:!Selected")).toEqual([matchingNode]);
  });

  it("matches non-selected uppercase in brackets", function() {
    var matchingNode = {
      $selected: false
    };
    var otherNode = {
      $selected: true
    };
    var nodes = [matchingNode, otherNode];
    expect(nodesFilter(nodes, "in:(!Selected)")).toEqual([matchingNode]);
  });

  it("matches on attribute", function() {
    var matchingNode = {
      hostname: "name"
    };
    var otherNode = {
      hostname: "other"
    };
    var nodes = [matchingNode, otherNode];
    expect(nodesFilter(nodes, "hostname:name")).toEqual([matchingNode]);
  });

  it("matches with contains on attribute", function() {
    var matchingNode = {
      hostname: "name"
    };
    var otherNode = {
      hostname: "other"
    };
    var nodes = [matchingNode, otherNode];
    expect(nodesFilter(nodes, "hostname:na")).toEqual([matchingNode]);
  });

  it("matches on negating attribute", function() {
    var matchingNode = {
      hostname: "name"
    };
    var otherNode = {
      hostname: "other"
    };
    var nodes = [matchingNode, otherNode];
    expect(nodesFilter(nodes, "hostname:!other")).toEqual([matchingNode]);
  });

  it("matches on exact attribute", function() {
    var matchingNode = {
      hostname: "other"
    };
    var otherNode = {
      hostname: "other2"
    };
    var nodes = [matchingNode, otherNode];
    expect(nodesFilter(nodes, "hostname:=other")).toEqual([matchingNode]);
  });

  it("matches on array", function() {
    var matchingNode = {
      hostnames: ["name", "first"]
    };
    var otherNode = {
      hostnames: ["other", "second"]
    };
    var nodes = [matchingNode, otherNode];
    expect(nodesFilter(nodes, "hostnames:first")).toEqual([matchingNode]);
  });

  it("matches integer values", function() {
    var matchingNode = {
      count: 4
    };
    var otherNode = {
      count: 2
    };
    var nodes = [matchingNode, otherNode];
    expect(nodesFilter(nodes, "count:3")).toEqual([matchingNode]);
  });

  it("matches float values", function() {
    var matchingNode = {
      count: 2.2
    };
    var otherNode = {
      count: 1.1
    };
    var nodes = [matchingNode, otherNode];
    expect(nodesFilter(nodes, "count:1.5")).toEqual([matchingNode]);
  });

  it("matches using cpu mapping function", function() {
    var matchingNode = {
      cpu_count: 4
    };
    var otherNode = {
      cpu_count: 2
    };
    var nodes = [matchingNode, otherNode];
    expect(nodesFilter(nodes, "cpu:3")).toEqual([matchingNode]);
  });

  it("matches using cores mapping function", function() {
    var matchingNode = {
      cpu_count: 4
    };
    var otherNode = {
      cpu_count: 2
    };
    var nodes = [matchingNode, otherNode];
    expect(nodesFilter(nodes, "cores:3")).toEqual([matchingNode]);
  });

  it("matches using ram mapping function", function() {
    var matchingNode = {
      memory: 2048
    };
    var otherNode = {
      memory: 1024
    };
    var nodes = [matchingNode, otherNode];
    expect(nodesFilter(nodes, "ram:2000")).toEqual([matchingNode]);
  });

  it("matches using mac mapping function", function() {
    var matchingNode = {
      pxe_mac: "00:11:22:33:44:55",
      extra_macs: ["aa:bb:cc:dd:ee:ff"]
    };
    var otherNode = {
      pxe_mac: "66:11:22:33:44:55",
      extra_macs: ["00:bb:cc:dd:ee:ff"]
    };
    var nodes = [matchingNode, otherNode];
    expect(nodesFilter(nodes, "mac:aa:bb:cc:dd:ee:ff")).toEqual([matchingNode]);
  });

  it("matches using zone mapping function", function() {
    var matchingNode = {
      zone: {
        name: "first"
      }
    };
    var otherNode = {
      zone: {
        name: "second"
      }
    };
    var nodes = [matchingNode, otherNode];
    expect(nodesFilter(nodes, "zone:first")).toEqual([matchingNode]);
  });

  it("matches using pool mapping function", function() {
    var matchingNode = {
      pool: {
        name: "pool1"
      }
    };
    var otherNode = {
      pool: {
        name: "pool2"
      }
    };
    var nodes = [matchingNode, otherNode];
    expect(nodesFilter(nodes, "pool:pool1")).toEqual([matchingNode]);
  });

  it("matches using pod mapping function", function() {
    var matchingNode = {
      pod: {
        name: "pod1"
      }
    };
    var otherNode = {
      pod: {
        name: "pod2"
      }
    };
    var nodes = [matchingNode, otherNode];
    expect(nodesFilter(nodes, "pod:pod1")).toEqual([matchingNode]);
  });

  it("matches using pod-id mapping function", function() {
    var matchingNode = {
      pod: {
        name: "pod1",
        id: 1
      }
    };
    var otherNode = {
      pod: {
        name: "pod2",
        id: 2
      }
    };
    var nodes = [matchingNode, otherNode];
    expect(nodesFilter(nodes, "pod-id:=1")).toEqual([matchingNode]);
  });

  it("matches using power mapping function", function() {
    var matchingNode = {
      power_state: "on"
    };
    var otherNode = {
      power_state: "off"
    };
    var nodes = [matchingNode, otherNode];
    expect(nodesFilter(nodes, "power:on")).toEqual([matchingNode]);
  });

  it("matches accumulate", function() {
    var matchingNode = {
      power_state: "on",
      zone: {
        name: "first"
      }
    };
    var otherNode = {
      power_state: "on",
      zone: {
        name: "second"
      }
    };
    var nodes = [matchingNode, otherNode];
    expect(nodesFilter(nodes, "power:on zone:first")).toEqual([matchingNode]);
  });

  it("matches a tag", function() {
    var matchingNode = {
      tags: ["first", "second"]
    };
    var otherNode = {
      tags: ["second", "third"]
    };
    var nodes = [matchingNode, otherNode];
    expect(nodesFilter(nodes, "tags:first")).toEqual([matchingNode]);
  });

  it("matches a negated tag", function() {
    var matchingNode = {
      tags: ["first", "second"]
    };
    var otherNode = {
      tags: ["second", "third"]
    };
    var nodes = [matchingNode, otherNode];
    expect(nodesFilter(nodes, "tags:!third")).toEqual([matchingNode]);
    expect(nodesFilter(nodes, "tags:!(third)")).toEqual([matchingNode]);
    expect(nodesFilter(nodes, "tags:(!third)")).toEqual([matchingNode]);
  });

  it("matches a double negated tag", function() {
    var matchingNode = {
      tags: ["first", "second"]
    };
    var otherNode = {
      tags: ["second", "third"]
    };
    var nodes = [matchingNode, otherNode];
    expect(nodesFilter(nodes, "tags:!!first")).toEqual([matchingNode]);
    expect(nodesFilter(nodes, "tags:!(!first)")).toEqual([matchingNode]);
    expect(nodesFilter(nodes, "tags:(!!first)")).toEqual([matchingNode]);
  });

  it("matches a direct and a negated tag", function() {
    var matchingNode = {
      tags: ["first", "second"]
    };
    var otherNode = {
      tags: ["second", "third"]
    };
    var nodes = [matchingNode, otherNode];
    expect(nodesFilter(nodes, "tags:(first,!third)")).toEqual([matchingNode]);
  });

  it("matches an exact direct and a negated tag", function() {
    var matchingNode = {
      tags: ["first", "second"]
    };
    var otherNode = {
      tags: ["first1", "third"]
    };
    var nodes = [matchingNode, otherNode];
    expect(nodesFilter(nodes, "tags:(=first,!third)")).toEqual([matchingNode]);
  });

  it("matches two negated tags", function() {
    var matchingNode = {
      tags: ["first", "second"]
    };
    var otherNode = {
      tags: ["second", "third"]
    };
    var nodes = [matchingNode, otherNode];
    expect(nodesFilter(nodes, "tags:(!second,!third)")).toEqual([matchingNode]);
  });

  it("matches using release mapping function", function() {
    var deployingNode = {
      status_code: 9,
      osystem: "ubuntu",
      distro_series: "xenial"
    };
    var deployedNode = {
      status_code: 6,
      osystem: "ubuntu",
      distro_series: "xenial"
    };
    var allocatedNode = {
      status_code: 5,
      osystem: "ubuntu",
      distro_series: "xenial"
    };
    var deployedOtherNode = {
      status_code: 6,
      osystem: "ubuntu",
      distro_series: "trusty"
    };
    var nodes = [deployingNode, deployedNode, allocatedNode, deployedOtherNode];
    expect(nodesFilter(nodes, "release:ubuntu/xenial")).toEqual([
      deployingNode,
      deployedNode
    ]);
  });
});
