/* Copyright 2019 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 *
 * Cores chart directive.
 */

/**
 *
 * @param {string} type
 * @param {array} classList
 */
function createElement(type, classList) {
  let el = document.createElement(type);

  if (classList) {
    el.classList.add(...classList);
  }

  return el;
}

/**
 *
 * @param {number} n
 */
function isOddNumber(n) {
  return n % 2 === 0;
}

/**
 *
 * @param {object} coresData
 * @param {object} classList
 */
function buildRows(coresData, classList) {
  let firstCoresRow = createElement("div", classList.row);
  let secondCoresRow = createElement("div", classList.row);
  let rows = [];

  if (coresData.totalCores <= coresData.maxCores) {
    for (let i = 0, ii = coresData.cores; i < ii; i++) {
      let core = createElement("span", classList.core);

      if (coresData.totalCores <= coresData.maxCoresPerRow) {
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

    if (coresData.totalCores > coresData.maxCoresPerRow) {
      rows.push(secondCoresRow);
    }
  } else {
    let bar = createElement("div", classList.bar);
    bar.style.width = (coresData.cores / coresData.totalCores) * 100 + "%";
    rows = [bar];
  }

  return rows;
}

/**
 *
 * @param {number} totalCores
 * @param {number} usedCores
 * @param {number} overcommitRatio
 */
function createChart(totalCores, usedCores, overcommitRatio) {
  const maxCores = 32;
  const maxCoresPerRow = 16;
  const overcommittedCores = totalCores * overcommitRatio;

  let coresDisplayCount = overcommitRatio < 1 ? totalCores : overcommittedCores;

  let chart = createElement("div", ["p-cores-chart"]);
  let chartInner = createElement("div", ["p-cores-chart__inner"]);
  let totalCoresWrapper = createElement("div", ["p-total-cores__wrapper"]);
  let usedCoresWrapper = createElement("div", ["p-used-cores__wrapper"]);

  let totalCoresClasses = {
    row: ["p-cores-row"],
    core: ["p-core", "p-core--total"],
    bar: ["p-cores-chart__total-bar"]
  };

  let usedCoresClasses = {
    row: ["p-cores-row--used"],
    core: ["p-core", "p-core--used"],
    bar: ["p-cores-chart__used-bar"]
  };

  let totalCoresRows = buildRows(
    {
      cores: coresDisplayCount,
      totalCores: coresDisplayCount,
      maxCores: maxCores,
      maxCoresPerRow: maxCoresPerRow
    },
    totalCoresClasses
  );

  let usedCoresRows = buildRows(
    {
      cores: usedCores,
      totalCores: coresDisplayCount,
      maxCores: maxCores,
      maxCoresPerRow: maxCoresPerRow
    },
    usedCoresClasses
  );

  totalCoresRows.forEach(row => {
    totalCoresWrapper.appendChild(row);
  });

  usedCoresRows.forEach(row => {
    usedCoresWrapper.appendChild(row);
  });

  if (totalCoresRows.length === 1 && coresDisplayCount <= maxCoresPerRow) {
    chart.classList.add("p-cores-chart--single-row");
  }

  if (totalCoresRows.length === 2) {
    chart.classList.add("p-cores-chart--double-row");
  }

  chartInner.appendChild(totalCoresWrapper);
  chartInner.appendChild(usedCoresWrapper);

  let chartBorder = createElement("div", ["p-cores-chart__border"]);

  if (overcommitRatio < 1) {
    chartBorder.style.width = (overcommittedCores / totalCores) * 100 + "%";
    chartBorder.classList.add("p-cores-chart__border--undercommit");
    chart.classList.add("p-cores-chart--undercommit");
  }

  if (overcommitRatio > 1) {
    let chartBorderOvercommit = createElement("div", [
      "p-cores-chart__border--overcommit"
    ]);

    chartBorderOvercommit.style.width =
      100 - (totalCores / overcommittedCores) * 100 + "%";
    chartBorder.style.width = (totalCores / overcommittedCores) * 100 + "%";

    chart.classList.add("p-cores-chart--overcommit");
    chart.appendChild(chartBorderOvercommit);
  }

  chart.appendChild(chartInner);
  chart.appendChild(chartBorder);

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
      used: "=",
      overcommit: "="
    },
    link: function(scope, element) {
      let el = createChart(scope.total, scope.used, scope.overcommit);
      element.html(el);
    }
  };
}
