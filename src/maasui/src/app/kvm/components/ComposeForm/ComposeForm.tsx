import type { ReactElement } from "react";
import { useCallback, useEffect, useState } from "react";

import { formatBytes } from "@canonical/maas-react-components";
import {
  NotificationSeverity,
  Spinner,
  Strip,
} from "@canonical/react-components";
import { useDispatch, useSelector } from "react-redux";
import * as Yup from "yup";

import ComposeFormFields from "./ComposeFormFields";
import InterfacesTable from "./InterfacesTable";
import StorageTable from "./StorageTable";

import { usePools } from "@/app/api/query/pools";
import { useZones } from "@/app/api/query/zones";
import type { ResourcePoolResponse } from "@/app/apiclient";
import ActionForm from "@/app/base/components/ActionForm";
import { useSidePanel } from "@/app/base/side-panel-context";
import { hostnameValidation, RANGE_REGEX } from "@/app/base/validation";
import { useActivePod } from "@/app/kvm/hooks";
import { domainActions } from "@/app/store/domain";
import domainSelectors from "@/app/store/domain/selectors";
import { fabricActions } from "@/app/store/fabric";
import fabricSelectors from "@/app/store/fabric/selectors";
import { generalActions } from "@/app/store/general";
import { powerTypes as powerTypesSelectors } from "@/app/store/general/selectors";
import { machineActions } from "@/app/store/machine";
import { messageActions } from "@/app/store/message";
import { podActions } from "@/app/store/pod";
import podSelectors from "@/app/store/pod/selectors";
import type { Pod } from "@/app/store/pod/types";
import {
  getCoreIndices,
  isPodDetails,
  resourceWithOverCommit,
} from "@/app/store/pod/utils";
import type { RootState } from "@/app/store/root/types";
import { spaceActions } from "@/app/store/space";
import spaceSelectors from "@/app/store/space/selectors";
import type { Space } from "@/app/store/space/types";
import { subnetActions } from "@/app/store/subnet";
import subnetSelectors from "@/app/store/subnet/selectors";
import type { Subnet } from "@/app/store/subnet/types";
import { vlanActions } from "@/app/store/vlan";
import vlanSelectors from "@/app/store/vlan/selectors";
import { arrayFromRangesString, getRanges } from "@/app/utils";

export type Disk = {
  location: string;
  size: number; // GB
  tags: string[];
};

export type DiskField = Disk & { id: number };

export type InterfaceField = {
  id: number;
  ipAddress?: string;
  name: string;
  space: string;
  subnet: string;
};

export type ComposeFormValues = {
  architecture: string;
  bootDisk: number;
  cores: number;
  disks: DiskField[];
  domain: string;
  hostname: string;
  hugepagesBacked: boolean;
  interfaces: InterfaceField[];
  memory: number;
  pinnedCores: string;
  pool: string;
  zone: string;
};

export type ComposeFormDefaults = {
  cores: number;
  disk: Disk;
  memory: number;
};

/**
 * Create interface constraints in the form <interface-name>:<key>=<value>[,<key>=<value>];....
 * e.g. "eth0:ip=192.168.0.0,subnet_cidr=192.168.0.0/24"
 * @param {InterfaceField[]} interfaces - The interfaces from which to create the constraints.
 * @param {Space[]} spaces - The spaces in state.
 * @param {Subnet[]} subnets - The subnets in state.
 * @returns {string} Interface constraints string.
 */
export const createInterfaceConstraints = (
  interfaces: InterfaceField[],
  spaces: Space[],
  subnets: Subnet[]
): string => {
  return interfaces
    .map((iface) => {
      const constraints: string[] = [];
      if (iface.ipAddress !== "") {
        constraints.push(`ip=${iface.ipAddress}`);
      }
      if (iface.space !== "") {
        const space = spaces.find(
          (space) => space.id === parseInt(iface.space)
        );
        !!space && constraints.push(`space=${space.name}`);
      }
      if (iface.subnet !== "") {
        const subnet = subnets.find(
          (subnet) => subnet.id === parseInt(iface.subnet)
        );
        !!subnet && constraints.push(`subnet_cidr=${subnet?.cidr}`);
      }
      if (constraints.length >= 1) {
        return `${iface.name}:${constraints.join(",")}`;
      }
      return "";
    })
    .filter(Boolean)
    .join(";");
};

/**
 * Create storage constraints in the form "<id>:<sizeGB>(<location>,<tag1>,<tag2>,...)"
 * e.g. "0:8(my-pool, tag1, tag2)"
 * @param {DiskField[]} disks - The disks from which to create the constraints.
 * @param {number} bootDiskID - The form id of the boot disk.
 * @returns {string} Storage constraints string.
 */
export const createStorageConstraints = (
  disks?: DiskField[],
  bootDiskID?: number
): string => {
  if (!disks || disks.length === 0) {
    return "";
  }

  // Sort disks so boot disk is first.
  let sortedDisks: DiskField[] = [];
  if (bootDiskID) {
    const bootDisk = disks.find((disk) => disk.id === bootDiskID);
    if (bootDisk) {
      sortedDisks.push(bootDisk);
    }
    sortedDisks = sortedDisks.concat(
      disks.filter((disk) => disk.id !== bootDiskID)
    );
  } else {
    sortedDisks = disks;
  }

  return sortedDisks
    .map((disk) => {
      return `${disk.id}:${disk.size}(${[disk.location, ...disk.tags].join(
        ","
      )})`;
    })
    .join(",");
};

/**
 * Get the default location of the first disk when form is mounted.
 * @param pod - The pod in which to determine default disk location.
 * @returns default disk location.
 */
export const getDefaultPoolLocation = (pod: Pod): string => {
  const defaultPool = pod.storage_pools?.find(
    (pool) => pool.id === pod.default_storage_pool
  );
  return defaultPool?.name || "";
};

type Props = {
  hostId: Pod["id"];
};

const ComposeForm = ({
  hostId,
  // eslint-disable-next-line complexity
}: Props): ReactElement => {
  const dispatch = useDispatch();
  const { closeSidePanel } = useSidePanel();

  const pod = useSelector((state: RootState) =>
    podSelectors.getById(state, hostId)
  );
  const errors = useSelector(podSelectors.errors);
  const composingPods = useSelector(podSelectors.composing);
  const domains = useSelector(domainSelectors.all);
  const domainsLoaded = useSelector(domainSelectors.loaded);
  const fabricsLoaded = useSelector(fabricSelectors.loaded);
  const pools = usePools();
  const powerTypes = useSelector(powerTypesSelectors.get);
  const powerTypesLoaded = useSelector(powerTypesSelectors.loaded);
  const spaces = useSelector(spaceSelectors.all);
  const spacesLoaded = useSelector(spaceSelectors.loaded);
  const subnets = useSelector(subnetSelectors.all);
  const subnetsLoaded = useSelector(subnetSelectors.loaded);
  const vlans = useSelector(vlanSelectors.all);
  const vlansLoaded = useSelector(vlanSelectors.loaded);
  const zones = useZones();
  const [machineName, setMachineName] = useState("");
  const cleanup = useCallback(() => podActions.cleanup(), []);
  useActivePod(hostId);

  useEffect(() => {
    dispatch(domainActions.fetch());
    dispatch(fabricActions.fetch());
    dispatch(generalActions.fetchPowerTypes());
    dispatch(podActions.get(hostId));
    dispatch(spaceActions.fetch());
    dispatch(subnetActions.fetch());
    dispatch(vlanActions.fetch());
  }, [dispatch, hostId]);
  const loaded =
    domainsLoaded &&
    fabricsLoaded &&
    !pools.isPending &&
    powerTypesLoaded &&
    spacesLoaded &&
    subnetsLoaded &&
    vlansLoaded &&
    !zones.isPending;

  if (isPodDetails(pod) && loaded) {
    const powerType = powerTypes.find((type) => type.name === pod.type);
    const { cpu_over_commit_ratio, memory_over_commit_ratio, resources } = pod;
    const { cores, memory } = resources;
    const { free: availableCores } = resourceWithOverCommit(
      cores,
      cpu_over_commit_ratio
    );
    const { free: availableGeneral } = resourceWithOverCommit(
      memory.general,
      memory_over_commit_ratio
    );
    const availableHugepages = memory.hugepages.free;
    const available = {
      cores: availableCores,
      hugepages: availableHugepages,
      memory: formatBytes(
        { value: availableGeneral + availableHugepages, unit: "B" },
        {
          binary: true,
          convertTo: "MiB",
        }
      ).value,
      pinnedCores: getCoreIndices(pod, "free"),
      storage:
        pod.storage_pools?.reduce<
          Record<
            ResourcePoolResponse["name"],
            ReturnType<typeof formatBytes>["value"]
          >
        >((available, pool) => {
          available[pool.name] = formatBytes(
            { value: pool.available, unit: "B" },
            {
              convertTo: "GB",
              roundFunc: "floor",
            }
          ).value;
          return available;
        }, {}) || [],
    };
    const defaultPoolLocation = getDefaultPoolLocation(pod);
    const defaults = {
      cores: powerType?.defaults?.cores || 1,
      disk: {
        location: defaultPoolLocation,
        size: powerType?.defaults?.storage || 8,
        tags: [],
      },
      memory: powerType?.defaults?.memory || 2048,
    };

    const ComposeFormSchema = Yup.object().shape({
      architecture: Yup.string().required("An architecture is required."),
      cores: Yup.number()
        .positive("Cores must be a positive number.")
        .min(1, "Cores must be a positive number.")
        .max(
          available.cores,
          available.cores <= 0
            ? "No cores available."
            : available.cores < defaults.cores
              ? `The available cores (${available.cores}) is less than the
                recommended default (${defaults.cores}).`
              : undefined
        ),
      disks: Yup.array()
        .of(
          Yup.object()
            .shape({
              id: Yup.number().required("ID is required"),
              location: Yup.string().required("Location is required"),
              size: Yup.number()
                .min(1, "At least 1GB required")
                .required("Size is required"),
              tags: Yup.array().of(Yup.string()),
            })
            .test("enoughSpace", "Not enough space", function test() {
              // This test validates whether there is enough space in the storage
              // pools for all disk requests. A functional expression is used
              // in order to use Yup's "this" context.
              // https://github.com/jquense/yup#mixedtestname-string-message-string--function-test-function-schema
              const disks: DiskField[] = this.parent || [];

              let error: Yup.ValidationError | null = null;
              disks.forEach((disk, i) => {
                const poolName = disk.location;
                const disksInPool = disks.filter(
                  (d) => d.location === poolName
                );
                const poolRequestTotal = disksInPool.reduce(
                  (total, d) => total + d.size,
                  0
                );
                const availableGB = available.storage[poolName];

                if (poolRequestTotal > availableGB) {
                  error = this.createError({
                    message: `Only ${availableGB}GB available in ${poolName}.`,
                    path: `disks[${i}].size`,
                  });
                }
              });
              return error || true;
            })
        )
        .min(1, "At least one disk is required"),
      domain: Yup.string(),
      hostname: hostnameValidation,
      hugepagesBacked: Yup.boolean(),
      interfaces: Yup.array().of(
        Yup.object()
          .shape({
            id: Yup.number().required("ID is required"),
            ipAddress: Yup.string(),
            name: Yup.string().required("Name is required"),
            space: Yup.string(),
            subnet: Yup.string().required("Subnet is required"),
          })
          .test("noPxe", "No PXE network selected", (_, context) => {
            const interfaces: InterfaceField[] = context.parent || [];

            if (interfaces.length > 1) {
              const hasPxe = interfaces.some((iface) => {
                const subnet = subnets.find(
                  (subnet) => subnet.id === Number(iface.subnet)
                );
                const vlan = vlans.find((vlan) => vlan.id === subnet?.vlan);
                return !!vlan && pod.boot_vlans.includes(vlan.id);
              });

              if (!hasPxe) {
                return context.createError({
                  message:
                    "Select at least 1 PXE network when creating multiple interfaces.",
                  path: `interfaces[${interfaces.length - 1}].subnet`,
                });
              }
            }
            return true;
          })
      ),
      memory: Yup.number()
        .positive("RAM must be a positive number.")
        .min(1024, "At least 1024 MiB is required.")
        .max(
          available.memory,
          available.memory <= 0
            ? "No memory available."
            : available.memory < defaults.memory
              ? `The available memory (${available.memory}MiB) is less than the
                recommended default (${defaults.memory}MiB).`
              : undefined
        ),
      pinnedCores: Yup.string()
        .matches(RANGE_REGEX, 'Cores string must follow format e.g "1,2,4-12"')
        .test("pinnedCores", "Check pinned cores string", (_, context) => {
          const { cores, pinnedCores } = context.parent;

          if (available.cores === 0) {
            return context.createError({
              message: "There are no cores available to pin.",
              path: "pinnedCores",
            });
          }
          // Don't proceed with pinned core validation if empty (default) values
          // are used or if cores are not being pinned.
          if ((!cores && !pinnedCores) || Boolean(cores)) {
            return true;
          }

          const selectedCores = arrayFromRangesString(pinnedCores || "") || [];
          const noneSelected = selectedCores.length === 0;
          const notEnoughAvailable = selectedCores.length > available.cores;
          const hasDuplicates = selectedCores.some(
            (core) =>
              selectedCores.indexOf(core) !== selectedCores.lastIndexOf(core)
          );
          const nonExistentCores = selectedCores.filter(
            (core) =>
              ![
                ...getCoreIndices(pod, "free"),
                ...getCoreIndices(pod, "allocated"),
              ].includes(core)
          );

          let errorMessage = "";
          if (noneSelected) {
            errorMessage = "No cores have been selected.";
          } else if (hasDuplicates) {
            errorMessage = "Duplicate core indices detected.";
          } else if (notEnoughAvailable) {
            errorMessage = `Number of cores requested (${selectedCores.length}) is more than available (${available.cores}).`;
          } else if (nonExistentCores.length > 0) {
            errorMessage = `The following cores do not exist on this host: ${getRanges(
              nonExistentCores
            )}`;
          }
          if (errorMessage) {
            return context.createError({
              message: errorMessage,
              path: "pinnedCores",
            });
          }
          return true;
        }),
      pool: Yup.string(),
      zone: Yup.string(),
    });

    return (
      <ActionForm<ComposeFormValues>
        actionName="compose"
        allowUnchanged
        aria-label="Compose VM"
        cleanup={cleanup}
        errors={errors}
        initialTouched={{
          architecture: true,
          cores: true,
          memory: true,
          pinnedCores: true,
        }}
        initialValues={{
          architecture: pod.architectures[0] || "",
          bootDisk: 1,
          cores: defaults.cores,
          disks: defaultPoolLocation ? [{ ...defaults.disk, id: 1 }] : [],
          domain: `${domains[0]?.id}` || "",
          hostname: "",
          hugepagesBacked: false,
          interfaces: [],
          memory: defaults.memory,
          pinnedCores: "",
          pool: `${pools.data?.items[0]?.id}` || "",
          zone: `${zones.data?.items[0]?.id}` || "",
        }}
        modelName="machine"
        onCancel={closeSidePanel}
        onSaveAnalytics={{
          action: "Submit",
          category: "KVM details action form",
          label: "Compose",
        }}
        onSubmit={(values: ComposeFormValues) => {
          // Remove any errors before dispatching compose action.
          dispatch(cleanup());
          const pinnedCoresArray = arrayFromRangesString(values.pinnedCores);

          const params = {
            architecture: values.architecture,
            domain: Number(values.domain),
            hostname: values.hostname,
            hugepages_backed: values.hugepagesBacked,
            id: pod.id,
            interfaces: createInterfaceConstraints(
              values.interfaces,
              spaces,
              subnets
            ),
            memory: values.memory,
            pool: Number(values.pool),
            storage: createStorageConstraints(values.disks, values.bootDisk),
            zone: Number(values.zone),
            ...(values.cores && { cores: values.cores }),
            ...(pinnedCoresArray && { pinned_cores: pinnedCoresArray }),
          };

          setMachineName(values.hostname || "Machine");
          dispatch(podActions.compose(params));
        }}
        onSuccess={() => {
          dispatch(
            messageActions.add(
              `${machineName} composed successfully.`,
              NotificationSeverity.INFORMATION
            )
          );
          dispatch(machineActions.invalidateQueries());
          closeSidePanel();
        }}
        processingCount={composingPods.length}
        selectedCount={1}
        showProcessingCount={false}
        validateOnMount
        validationSchema={ComposeFormSchema}
      >
        <Strip bordered className="u-no-padding--top" shallow>
          <ComposeFormFields
            architectures={pod.architectures}
            available={available}
            defaults={defaults}
            podType={pod.type}
          />
        </Strip>
        <Strip bordered shallow>
          <InterfacesTable hostId={pod.id} />
        </Strip>
        <Strip shallow>
          <StorageTable defaultDisk={defaults.disk} hostId={pod.id} />
        </Strip>
      </ActionForm>
    );
  }
  return (
    <Strip>
      <Spinner text="Loading..." />
    </Strip>
  );
};

export default ComposeForm;
