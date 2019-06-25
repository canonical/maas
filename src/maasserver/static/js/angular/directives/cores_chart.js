/* Copyright 2019 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 *
 * Cores chart directive.
 */

function createElement(type, classList) {
  var el = document.createElement(type);

  if (classList) {
    // Could use the spread operator here to avoid this
    // loop but can't be bothered to setup babel here
    // e.g. classList.add(...classList)
    classList.forEach(function(cls) {
      el.classList.add(cls);
    });
  }

  return el;
}

function isOddNumber(n) {
  return n % 2 === 0;
}

function buildRows(coresData, classList) {
  var firstCoresRow = createElement("div", classList.row);
  var secondCoresRow = createElement("div", classList.row);
  var rows = [];

  if (coresData.totalCores <= coresData.maxCores) {
    for (var i = 0, ii = coresData.cores; i < ii; i++) {
      var core = createElement("span", classList.core);

      if (coresData.totalCores <= coresData.coresPerRow) {
        if (i < coresData.totalCores) {
          firstCoresRow.appendChild(core);
        }
      } else {
        if (i < coresData.totalCores) {
          if (isOddNumber(i)) {
            firstCoresRow.appendChild(core);
          }

          if (!isOddNumber(i)) {
            secondCoresRow.appendChild(core);
          }
        }
      }
    }

    rows.push(firstCoresRow);

    if (coresData.totalCores > coresData.coresPerRow) {
      rows.push(secondCoresRow);
    }
  } else {
    var bar = createElement("div", classList.bar);
    bar.style.width = (coresData.cores / coresData.totalCores) * 100 + "%";
    rows = [bar];
  }

  return rows;
}

function createChart(total, used) {
  var chart = createElement("div", ["p-cores-chart"]);
  var chartInner = createElement("div", ["p-cores-chart__inner"]);
  var maxCores = 32;
  var coresPerRow = 16;

  var totalCoresClasses = {
    row: ["p-cores-row"],
    core: ["p-core"],
    bar: ["p-cores-chart__total-bar"]
  };

  var usedCoresClasses = {
    row: ["p-cores-row--used"],
    core: ["p-core", "p-core--used"],
    bar: ["p-cores-chart__used-bar"]
  };

  var totalCoresRows = buildRows(
    {
      cores: total,
      totalCores: total,
      maxCores: maxCores,
      coresPerRow: coresPerRow
    },
    totalCoresClasses
  );

  var usedCoresRows = buildRows(
    {
      cores: used,
      totalCores: total,
      maxCores: maxCores,
      coresPerRow: coresPerRow
    },
    usedCoresClasses
  );

  totalCoresRows.forEach(function(row) {
    chartInner.appendChild(row);
  });

  usedCoresRows.forEach(function(row) {
    chartInner.appendChild(row);
  });

  if (totalCoresRows.length === 1 && total <= coresPerRow) {
    chart.classList.add("p-cores-chart--single-row");
  }

  if (totalCoresRows.length === 2) {
    chart.classList.add("p-cores-chart--double-row");
  }

  chart.appendChild(chartInner);

  return chart;
}

/* @ngInject */
export function cacheCoresChart($templateCache) {
  $templateCache.put(
    "directive/templates/cores-chart.html",
    "<div class='p-cores-chart'></div>"
  );
}

/* @ngInject */
export function maasCoresChart() {
  return {
    restrict: "E",
    templateUrl: "directive/templates/cores-chart.html",
    scope: {
      total: "=",
      used: "="
    },
    link: function(scope, element) {
      var el = createChart(scope.total, scope.used);
      element.html(el);
    }
  };
}
