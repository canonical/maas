

angular.module('MAAS').filter('range', function() {
  return function(n) {
      var res = [];
      if (typeof n != 'number') {
        return res;
      }
      for (var i = 0; i < n; i++) {
          res.push(i);
      }
      return res;
  };
});