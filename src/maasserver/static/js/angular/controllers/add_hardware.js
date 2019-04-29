/* Copyright 2015-2018 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 *
 * MAAS Add Hardware Controller
 */

/* @ngInject */
function AddHardwareController(
  $q,
  $scope,
  $http,
  ZonesManager,
  ResourcePoolsManager,
  MachinesManager,
  GeneralManager,
  DomainsManager,
  ManagerHelperService,
  ValidationService
) {
  // Set the addHardwareScope in the parent, so it can call functions
  // in this controller.
  var parentScope = $scope.$parent;
  parentScope.addHardwareScope = $scope;

  // Set initial values.
  $scope.machineManager = MachinesManager;
  $scope.newMachineObj = {};
  $scope.viewable = false;
  $scope.model = "machine";
  $scope.zones = ZonesManager.getItems();
  $scope.pools = ResourcePoolsManager.getItems();
  $scope.domains = DomainsManager.getItems();
  $scope.architectures = GeneralManager.getData("architectures");
  $scope.architectures.push("Choose an architecture");
  $scope.hwe_kernels = GeneralManager.getData("hwe_kernels");
  $scope.default_min_hwe_kernel = GeneralManager.getData(
    "default_min_hwe_kernel"
  );
  $scope.power_types = GeneralManager.getData("power_types");
  $scope.error = null;
  $scope.macAddressRegex = /^([0-9A-F]{2}[::]){5}([0-9A-F]{2})$/gim;

  // Input values.
  $scope.machine = null;
  $scope.chassis = null;

  // Hard coded chassis types. This is because there is no method in
  // MAAS to get a full list of supported chassis. This needs to be
  // fixed ASAP.
  var virshFields = [
    {
      name: "hostname",
      label: "Address",
      field_type: "string",
      default: "", // Using "default" to make lint happy.
      choices: [],
      required: true
    },
    {
      name: "password",
      label: "Password",
      field_type: "string",
      default: "",
      choices: [],
      required: false
    },
    {
      name: "prefix_filter",
      label: "Prefix filter",
      field_type: "string",
      default: "",
      choices: [],
      required: false
    }
  ];
  $scope.chassisPowerTypes = [
    {
      name: "mscm",
      description: "Moonshot Chassis Manager",
      fields: [
        {
          name: "hostname",
          label: "Host",
          field_type: "string",
          default: "",
          choices: [],
          required: true
        },
        {
          name: "username",
          label: "Username",
          field_type: "string",
          default: "",
          choices: [],
          required: true
        },
        {
          name: "password",
          label: "Password",
          field_type: "string",
          default: "",
          choices: [],
          required: true
        }
      ]
    },
    {
      name: "powerkvm",
      description: "PowerKVM",
      fields: virshFields
    },
    {
      name: "recs_box",
      description: "Christmann RECS|Box",
      fields: [
        {
          name: "hostname",
          label: "Hostname",
          field_type: "string",
          default: "",
          choices: [],
          required: true
        },
        {
          name: "port",
          label: "Port",
          field_type: "string",
          default: "80",
          choices: [],
          required: false
        },
        {
          name: "username",
          label: "Username",
          field_type: "string",
          default: "",
          choices: [],
          required: true
        },
        {
          name: "password",
          label: "Password",
          field_type: "string",
          default: "",
          choices: [],
          required: true
        }
      ]
    },
    {
      name: "seamicro15k",
      description: "SeaMicro 15000",
      fields: [
        {
          name: "hostname",
          label: "Hostname",
          field_type: "string",
          default: "",
          choices: [],
          required: true
        },
        {
          name: "username",
          label: "Username",
          field_type: "string",
          default: "",
          choices: [],
          required: true
        },
        {
          name: "password",
          label: "Password",
          field_type: "string",
          default: "",
          choices: [],
          required: true
        },
        {
          name: "power_control",
          label: "Power Control",
          field_type: "choice",
          default: "restapi2",
          choices: [
            ["restapi2", "REST API V2.0"],
            ["restapi", "REST API V0.9"],
            ["ipmi", "IPMI"]
          ],
          required: true
        }
      ]
    },
    {
      name: "ucsm",
      description: "UCS Chassis Manager",
      fields: [
        {
          name: "hostname",
          label: "URL",
          field_type: "string",
          default: "",
          choices: [],
          required: true
        },
        {
          name: "username",
          label: "Username",
          field_type: "string",
          default: "",
          choices: [],
          required: true
        },
        {
          name: "password",
          label: "Password",
          field_type: "string",
          default: "",
          choices: [],
          required: true
        }
      ]
    },
    {
      name: "virsh",
      description: "Virsh (virtual systems)",
      fields: virshFields
    },
    {
      name: "vmware",
      description: "VMware",
      fields: [
        {
          name: "hostname",
          label: "Host",
          field_type: "string",
          default: "",
          choices: [],
          required: true
        },
        {
          name: "username",
          label: "Username",
          field_type: "string",
          default: "",
          choices: [],
          required: true
        },
        {
          name: "password",
          label: "Password",
          field_type: "string",
          default: "",
          choices: [],
          required: true
        },
        {
          name: "prefix_filter",
          label: "Prefix filter",
          field_type: "string",
          default: "",
          choices: [],
          required: false
        }
      ]
    }
  ];

  // Get the default zone from the loaded zones.
  function defaultZone() {
    if ($scope.zones.length === 0) {
      return null;
    } else {
      return $scope.zones[0];
    }
  }

  // Get the default resource pools from loaded pools.
  function defaultResourcePool() {
    if ($scope.pools.length === 0) {
      return null;
    } else {
      return $scope.pools[0];
    }
  }

  // Get the default architecture from the loaded architectures.
  function defaultArchitecture() {
    if ($scope.architectures.length === 0) {
      return "";
    } else {
      // Return amd64/generic first if available.
      var i;
      for (i = 0; i < $scope.architectures.length; i++) {
        if ($scope.architectures[i] === "amd64/generic") {
          return $scope.architectures[i];
        }
      }
      return $scope.architectures[0];
    }
  }

  // Return a new MAC address object.
  function newMAC() {
    return {
      mac: "",
      error: false
    };
  }

  // Return a new machine object.
  function newMachine(cloneMachine) {
    // Clone the machine instead of just creating a new one.
    // This helps the user by already having the previous selected
    // items selected for the new machine.
    if (angular.isObject(cloneMachine)) {
      return {
        name: "",
        domain: cloneMachine.domain,
        macs: [newMAC()],
        zone: cloneMachine.zone,
        pool: cloneMachine.pool,
        architecture: cloneMachine.architecture,
        min_hwe_kernel: cloneMachine.min_hwe_kernel,
        power: {
          type: cloneMachine.power.type,
          parameters: {}
        }
      };
    }

    // No clone machine. So create a new blank machine.
    return {
      name: "",
      domain: DomainsManager.getDefaultDomain(),
      macs: [newMAC()],
      zone: defaultZone(),
      pool: defaultResourcePool(),
      architecture: defaultArchitecture(),
      min_hwe_kernel: $scope.default_min_hwe_kernel.text,
      power: {
        type: null,
        parameters: {}
      }
    };
  }

  // Return a new chassis object.
  function newChassis(cloneChassis) {
    // Clone the chassis instead of just creating a new one.
    // This helps the user by already having the previous selected
    // items selected for the new machine.
    if (angular.isObject(cloneChassis)) {
      return {
        domain: cloneChassis.domain,
        power: {
          type: null,
          parameters: {}
        }
      };
    } else {
      return {
        domain: DomainsManager.getDefaultDomain(),
        power: {
          type: null,
          parameters: {}
        }
      };
    }
  }

  // Validate that all the parameters are there for the given power type.
  function powerParametersHasError(power_type, parameters) {
    var i;
    for (i = 0; i < power_type.fields.length; i++) {
      var field = power_type.fields[i];
      var value = parameters[field.name];
      if (field.required) {
        if (angular.isUndefined(value) || value === "") {
          return true;
        }
      }
    }
    return false;
  }

  // Called by the parent scope when this controller is viewable.
  $scope.show = function(mode) {
    $scope.mode = mode;

    // Exit early if already viewable.
    if ($scope.viewable) {
      return;
    }

    var loadedItems = false,
      loadedManagers = false;
    var defer = $q.defer();
    defer.promise.then(function() {
      // Add the first machine and chassis.
      $scope.machine = newMachine($scope.machine);
      $scope.chassis = newChassis($scope.chassis);
      $scope.error = null;

      // If the machine doesn't have an architecture
      // set then it was created before all of the
      // architectures were loaded. Set the default
      // architecture for that machine.
      if (
        angular.isObject($scope.machine) &&
        $scope.machine.architecture === ""
      ) {
        $scope.machine.architecture = defaultArchitecture();
      }
      $scope.viewable = true;
    });

    // The parent scope has already loaded the GeneralManager. If the
    // general manager is reloaded all items from the parents scope
    // will be reloaded as well. Call loadItems so only the items
    // the add hardware form cares about are loaded.
    GeneralManager.loadItems([
      "architectures",
      "hwe_kernels",
      "default_min_hwe_kernel"
    ]).then(function() {
      loadedItems = true;
      if (loadedManagers) {
        defer.resolve();
      }
    });
    ManagerHelperService.loadManagers($scope, [
      ZonesManager,
      DomainsManager
    ]).then(function() {
      loadedManagers = true;
      if (loadedItems) {
        defer.resolve();
      }
    });
  };

  // Called by the parent scope when this controller is hidden.
  $scope.hide = function() {
    $scope.viewable = false;

    ManagerHelperService.unloadManagers($scope, [ZonesManager, DomainsManager]);

    // Emit the hidden event.
    $scope.$emit("addHardwareHidden");
  };

  // Return True when architectures loaded and in machine mode.
  $scope.showMachine = function() {
    if ($scope.architectures.length === 0) {
      return false;
    }
    return $scope.mode === "machine";
  };

  // Return True when architectures loaded and in chassis mode.
  $scope.showChassis = function() {
    if ($scope.architectures.length === 0) {
      return false;
    }
    return $scope.mode === "chassis";
  };

  // Add a new MAC address to the machine.
  $scope.addMac = function() {
    $scope.machine.macs.push(newMAC());
  };

  // Remove a MAC address to the machine.
  $scope.removeMac = function(mac) {
    var idx = $scope.machine.macs.indexOf(mac);
    if (idx > -1) {
      $scope.machine.macs.splice(idx, 1);
    }
  };

  // Return true if the machine name is invalid.
  $scope.invalidName = function() {
    // Not invalid if empty.
    if ($scope.machine.name.length === 0) {
      return false;
    }
    return !ValidationService.validateHostname($scope.machine.name);
  };

  // Validate that the mac address is valid.
  $scope.validateMac = function(mac) {
    if (mac.mac === "") {
      mac.error = false;
    } else {
      mac.error = !ValidationService.validateMAC(mac.mac);
    }
  };

  // Return true when the machine is missing information or invalid
  // information.
  $scope.machineHasError = function() {
    // Early-out for errors.
    let in_error =
      $scope.machine === null ||
      $scope.machine.zone === null ||
      $scope.machine.pool === null ||
      ($scope.machine.architecture === "Choose an architecture" &&
        $scope.machine.power.type.name !== "ipmi") ||
      $scope.machine.power.type === null ||
      $scope.invalidName($scope.machine);
    if (in_error) {
      return in_error;
    }

    // Make sure none of the mac addresses are in error. The first one
    // cannot be blank the remaining are allowed to be empty.
    if (
      ($scope.machine.macs[0].mac === "" &&
        $scope.machine.power.type.name !== "ipmi") ||
      $scope.machine.macs[0].error
    ) {
      return true;
    }
    var i;
    for (i = 1; i < $scope.machine.macs.length; i++) {
      var mac = $scope.machine.macs[i];
      if (mac.mac !== "" && mac.error) {
        return true;
      }
    }
    return false;
  };

  // Return true if the chassis has errors.
  $scope.chassisHasErrors = function() {
    // Early-out for errors.
    let in_error =
      $scope.chassis === null || $scope.chassis.power.type === null;
    if (in_error) {
      return in_error;
    }
    return powerParametersHasError(
      $scope.chassis.power.type,
      $scope.chassis.power.parameters
    );
  };

  // Called when the cancel button is pressed.
  $scope.cancel = function() {
    $scope.machine = newMachine();
    $scope.chassis = newChassis();

    // Hide the controller.
    $scope.hide();

    $scope.showErrors = false;
  };

  // Converts machine information for macs and power from how
  // it is held in the UI to how it is handled over the websocket.
  function convertMachineToProtocol(machine) {
    // Convert the mac addresses.
    var macs = angular.copy(machine.macs);
    var pxe_mac = macs.shift().mac;
    var extra_macs = macs.map(function(mac) {
      return mac.mac;
    });

    // Return the new object.
    return {
      name: machine.name,
      domain: machine.domain,
      architecture: machine.architecture,
      min_hwe_kernel: machine.min_hwe_kernel,
      pxe_mac: pxe_mac,
      extra_macs: extra_macs,
      power_type: machine.power.type.name,
      power_parameters: angular.copy(machine.power.parameters),
      zone: {
        id: machine.zone.id,
        name: machine.zone.name
      },
      pool: {
        id: machine.pool.id,
        name: machine.pool.name
      }
    };
  }

  // Called to update maas-obj-form state with protocol
  // for macs and power.
  $scope.saveMachine = function(addAnother) {
    $scope.addAnother = addAnother;
    $scope.showErrors = true;

    // set maas-obj-form object;
    $scope.newMachineObj = Object.assign(
      $scope.newMachineObj,
      convertMachineToProtocol($scope.machine)
    );
  };

  // maas-obj-form after-save callback
  $scope.afterSaveMachine = function() {
    if ($scope.addAnother) {
      $scope.machine = newMachine($scope.machine);
    } else {
      $scope.machine = newMachine();

      // Hide the scope if not adding another.
      $scope.hide();
    }
  };

  // Called to perform the saving of the chassis.
  $scope.saveChassis = function(addAnother) {
    // Does nothing if error exists.
    if ($scope.chassisHasErrors()) {
      return;
    }

    // Clear the error so it can be set again, if it fails to save
    // the device.
    $scope.error = null;

    // Create the parameters.
    var params = angular.copy($scope.chassis.power.parameters);
    params.chassis_type = $scope.chassis.power.type.name;
    params.domain = $scope.chassis.domain.name;

    // XXX ltrager 24-02-2016: Something is adding the username field
    // even though its not defined in virshFields. The API rejects
    // requests with improper fields so remove it before we send the
    // request.
    if (params.chassis_type === "powerkvm" || params.chassis_type === "virsh") {
      delete params.username;
    }
    // Add the chassis. For now we use the API as the websocket doesn't
    // support probe and enlist.
    $http({
      method: "POST",
      url: "api/2.0/machines/?op=add_chassis",
      data: $.param(params),
      headers: {
        "Content-Type": "application/x-www-form-urlencoded"
      }
    }).then(
      function() {
        if (addAnother) {
          $scope.chassis = newChassis($scope.chassis);
        } else {
          $scope.chassis = newChassis();
          // Hide the scope if not adding another.
          $scope.hide();
        }
      },
      function(error) {
        $scope.error = ManagerHelperService.parseValidationError(error.data);
      }
    );
  };
}

export default AddHardwareController;
