import type { RouterState } from "redux-first-history";

import type { ConfigState, ConfigMeta } from "@/app/store/config/types";
import type {
  ControllerState,
  ControllerMeta,
} from "@/app/store/controller/types";
import type { DeviceState, DeviceMeta } from "@/app/store/device/types";
import type {
  DHCPSnippetState,
  DHCPSnippetMeta,
} from "@/app/store/dhcpsnippet/types";
import type { DomainState, DomainMeta } from "@/app/store/domain/types";
import type { EventState, EventMeta } from "@/app/store/event/types";
import type { FabricState, FabricMeta } from "@/app/store/fabric/types";
import type { GeneralState, GeneralMeta } from "@/app/store/general/types";
import type { IPRangeState, IPRangeMeta } from "@/app/store/iprange/types";
import type {
  LicenseKeysState,
  LicenseKeysMeta,
} from "@/app/store/licensekeys/types";
import type { MachineState, MachineMeta } from "@/app/store/machine/types";
import type { MessageState, MessageMeta } from "@/app/store/message/types";
import type { MsmState } from "@/app/store/msm/types/base";
import type { MsmMeta } from "@/app/store/msm/types/enum";
import type {
  NodeDeviceState,
  NodeDeviceMeta,
} from "@/app/store/nodedevice/types";
import type {
  NodeScriptResultState,
  NodeScriptResultMeta,
} from "@/app/store/nodescriptresult/types";
import type {
  NotificationState,
  NotificationMeta,
} from "@/app/store/notification/types";
import type {
  PackageRepositoryState,
  PackageRepositoryMeta,
} from "@/app/store/packagerepository/types";
import type { PodState, PodMeta } from "@/app/store/pod/types";
import type { ReservedIpState } from "@/app/store/reservedip/types";
import type { ReservedIpMeta } from "@/app/store/reservedip/types/enum";
import type { ScriptState, ScriptMeta } from "@/app/store/script/types";
import type {
  ScriptResultState,
  ScriptResultMeta,
} from "@/app/store/scriptresult/types";
import type { ServiceState, ServiceMeta } from "@/app/store/service/types";
import type { SpaceState, SpaceMeta } from "@/app/store/space/types";
import type {
  StaticRouteState,
  StaticRouteMeta,
} from "@/app/store/staticroute/types";
import type { StatusState, StatusMeta } from "@/app/store/status/types";
import type { SubnetState, SubnetMeta } from "@/app/store/subnet/types";
import type { TagState, TagMeta } from "@/app/store/tag/types";
import type { TokenState, TokenMeta } from "@/app/store/token/types";
import type { VLANState, VLANMeta } from "@/app/store/vlan/types";
import type {
  VMClusterMeta,
  VMClusterState,
} from "@/app/store/vmcluster/types";

export type RootState = {
  [ConfigMeta.MODEL]: ConfigState;
  [ControllerMeta.MODEL]: ControllerState;
  [DeviceMeta.MODEL]: DeviceState;
  [DHCPSnippetMeta.MODEL]: DHCPSnippetState;
  [DomainMeta.MODEL]: DomainState;
  [EventMeta.MODEL]: EventState;
  [FabricMeta.MODEL]: FabricState;
  [GeneralMeta.MODEL]: GeneralState;
  [IPRangeMeta.MODEL]: IPRangeState;
  [LicenseKeysMeta.MODEL]: LicenseKeysState;
  [MachineMeta.MODEL]: MachineState;
  [MessageMeta.MODEL]: MessageState;
  [MsmMeta.MODEL]: MsmState;
  [NodeDeviceMeta.MODEL]: NodeDeviceState;
  [NodeScriptResultMeta.MODEL]: NodeScriptResultState;
  [NotificationMeta.MODEL]: NotificationState;
  [PackageRepositoryMeta.MODEL]: PackageRepositoryState;
  [PodMeta.MODEL]: PodState;
  [ReservedIpMeta.MODEL]: ReservedIpState;
  router: RouterState;
  [ScriptResultMeta.MODEL]: ScriptResultState;
  [ScriptMeta.MODEL]: ScriptState;
  [ServiceMeta.MODEL]: ServiceState;
  [SpaceMeta.MODEL]: SpaceState;
  [StaticRouteMeta.MODEL]: StaticRouteState;
  [StatusMeta.MODEL]: StatusState;
  [SubnetMeta.MODEL]: SubnetState;
  [TagMeta.MODEL]: TagState;
  [TokenMeta.MODEL]: TokenState;
  [VLANMeta.MODEL]: VLANState;
  [VMClusterMeta.MODEL]: VMClusterState;
};
