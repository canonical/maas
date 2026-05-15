import type { PayloadAction } from "@reduxjs/toolkit";
import ReconnectingWebSocket from "reconnecting-websocket";

import type { AnyObject } from "@/app/base/types";
import { getCookie } from "@/app/utils";

// ESLint complains that this is only used as a type, but several types
// are derived from this in different ways, so it's cleaner to just have this as is.
// eslint-disable-next-line unused-imports/no-unused-vars
const WebSocketEndpoints = {
  bootresource: [
    "delete_image",
    "fetch",
    "poll",
    "save_other",
    "save_ubuntu",
    "save_ubuntu_core",
    "stop_import",
  ],
  config: ["bulk_update", "get", "list", "update"],
  controller: [
    "action",
    "check_images",
    "create",
    "get",
    "get_latest_failed_testing_script_results",
    "get_summary_xml",
    "get_summary_yaml",
    "list",
    "set_active",
    "set_script_result_suppressed",
    "set_script_result_unsuppressed",
    "update",
    "update_interface",
  ],
  device: [
    "action",
    "create",
    "create_interface",
    "create_physical",
    "delete_interface",
    "get",
    "link_subnet",
    "list",
    "set_active",
    "unlink_subnet",
    "update",
    "update_interface",
  ],
  dhcpsnippet: ["create", "delete", "get", "list", "revert", "update"],
  discovery: ["clear", "delete_by_mac_and_ip", "get", "list"],
  domain: [
    "create",
    "create_address_record",
    "create_dnsdata",
    "create_dnsresource",
    "delete",
    "delete_address_record",
    "delete_dnsdata",
    "delete_dnsresource",
    "get",
    "list",
    "set_active",
    "set_default",
    "update",
    "update_address_record",
    "update_dnsdata",
    "update_dnsresource",
  ],
  event: ["clear", "list"],
  fabric: ["create", "delete", "get", "list", "set_active", "update"],
  general: [
    "architectures",
    "bond_options",
    "components_to_disable",
    "default_min_hwe_kernel",
    "device_actions",
    "generate_client_certificate",
    "hwe_kernels",
    "install_type",
    "known_architectures",
    "known_boot_architectures",
    "machine_actions",
    "min_hwe_kernels",
    "osinfo",
    "pockets_to_disable",
    "power_types",
    "rack_controller_actions",
    "random_hostname",
    "region_and_rack_controller_actions",
    "region_controller_actions",
    "release_options",
    "target_version",
    "tls_certificate",
    "vault_enabled",
    "version",
  ],
  iprange: ["create", "delete", "get", "list", "update"],
  machine: [
    "action",
    "apply_storage_layout",
    "check_power",
    "count",
    "create",
    "create_bcache",
    "create_bond",
    "create_bridge",
    "create_cache_set",
    "create_logical_volume",
    "create_partition",
    "create_physical",
    "create_raid",
    "create_vlan",
    "create_vmfs_datastore",
    "create_volume_group",
    "default_user",
    "delete_cache_set",
    "delete_disk",
    "delete_filesystem",
    "delete_interface",
    "delete_partition",
    "delete_vmfs_datastore",
    "delete_volume_group",
    "filter_groups",
    "filter_options",
    "get",
    "get_latest_failed_testing_script_results",
    "get_summary_xml",
    "get_summary_yaml",
    "get_workload_annotations",
    "link_subnet",
    "list",
    "list_ids",
    "mount_special",
    "set_active",
    "set_boot_disk",
    "set_script_result_suppressed",
    "set_script_result_unsuppressed",
    "set_workload_annotations",
    "unlink_subnet",
    "unmount_special",
    "unsubscribe",
    "update",
    "update_disk",
    "update_filesystem",
    "update_interface",
    "update_vmfs_datastore",
  ],
  node_device: ["delete", "list"],
  node_result: ["clear", "get", "get_history", "get_result_data", "list"],
  packagerepository: ["create", "delete", "get", "list", "update"],
  pod: [
    "compose",
    "create",
    "delete",
    "get",
    "get_projects",
    "list",
    "refresh",
    "set_active",
    "update",
  ],
  resourcepool: ["create", "delete", "get", "list", "update"],
  script: ["delete", "get_script", "list"],
  service: ["get", "list", "set_active"],
  space: ["create", "delete", "get", "list", "set_active", "update"],
  sshkey: ["create", "delete", "get", "import_keys", "list"],
  sslkey: ["create", "delete", "get", "list"],
  staticroute: ["create", "delete", "get", "list", "update"],
  status: ["ping"],
  subnet: ["create", "delete", "get", "list", "scan", "set_active", "update"],
  tag: ["create", "delete", "get", "list", "update"],
  token: ["create", "delete", "get", "list", "update"],
  user: [
    "admin_change_password",
    "auth_user",
    "change_password",
    "create",
    "delete",
    "get",
    "list",
    "mark_intro_complete",
    "update",
  ],
  vlan: [
    "configure_dhcp",
    "create",
    "delete",
    "get",
    "list",
    "set_active",
    "update",
  ],
  vmcluster: ["delete", "get", "list", "list_by_physical_cluster", "update"],
  zone: ["create", "delete", "get", "list", "set_active", "update"],
} as const;

export type WebSocketEndpointModel = keyof typeof WebSocketEndpoints;
export type WebSocketEndpointMethod =
  (typeof WebSocketEndpoints)[WebSocketEndpointModel][number];

export type WebSocketEndpoint =
  `${WebSocketEndpointModel}.${WebSocketEndpointMethod}`;

// Message types defined by MAAS websocket API.
export enum WebSocketMessageType {
  REQUEST = 0,
  RESPONSE = 1,
  NOTIFY = 2,
  PING = 3,
  PING_REPLY = 4,
}

export enum WebSocketResponseType {
  SUCCESS = 0,
  ERROR = 1,
}

type WebSocketMessage = {
  request_id: number;
};

export type WebSocketRequestMessage = {
  method: WebSocketEndpoint;
  type: WebSocketMessageType;
  params?: Record<string, unknown> | Record<string, unknown>[];
};

export type WebSocketPingMessage = {
  type: WebSocketMessageType.PING;
};

export type WebSocketRequest = WebSocketMessage & WebSocketRequestMessage;

export type WebSocketResponseResult<R = unknown> = WebSocketMessage & {
  result: R;
  rtype: WebSocketResponseType.SUCCESS;
  type: WebSocketMessageType;
};

export type WebSocketResponseError = WebSocketMessage & {
  // The error might be a message or JSON.
  error: string;
  rtype: WebSocketResponseType.ERROR;
  type: WebSocketMessageType.RESPONSE;
};

export type WebSocketResponseNotify = {
  action: string;
  // The data will be parsed from JSON.
  data: unknown;
  name: string;
  type: WebSocketMessageType.NOTIFY;
};

export type WebSocketResponsePing = WebSocketResponseResult<number> & {
  type: WebSocketMessageType.PING_REPLY;
};

export type WebSocketActionParams = AnyObject | AnyObject[];

export type WebSocketAction<P = WebSocketActionParams> = PayloadAction<
  {
    params: P;
  } | null,
  string,
  {
    // Whether the request should only be fetched the first time.
    cache?: boolean;
    // Whether each item in the params should be dispatched separately. The
    // params need to be an array for this to work.
    dispatchMultiple?: boolean;
    // A key to be used to identify a file in the file context.
    fileContextKey?: string;
    // A key used to identify a websocket response. This is commonly the primary
    // key of a model in order to track a its loading/success/error states.
    identifier?: number | string;
    // The endpoint method e.g. "list".
    method: WebSocketEndpointMethod;
    // The endpoint model e.g. "machine".
    model: WebSocketEndpointModel;
    // Whether the request should be fetched every time.
    nocache?: boolean;
    // Whether the request should be polled.
    poll?: boolean;
    // An id for the polling request. This can be used to have multiple polling
    // events for the same endpoint.
    pollId?: string;
    // The amount of time in milliseconds between requests.
    pollInterval?: number;
    // An id to identify this request.
    callId?: string;
    // Whether polling should be stopped for the request.
    pollStop?: boolean;
    // Whether the request should unsubscribe from unused entities.
    unsubscribe?: boolean;
    // Whether the response should be stored in the file context.
    useFileContext?: boolean;
  }
>;

export class WebSocketClient {
  _nextId: WebSocketRequest["request_id"];
  _requests: Map<WebSocketRequest["request_id"], WebSocketAction>;
  rws: ReconnectingWebSocket | null;

  constructor() {
    this._nextId = 0;
    this._requests = new Map();
    this.rws = null;
  }

  /**
   * Dynamically build a websocket url from window.location
   * @param {string} csrftoken - A csrf token string.
   * @return {string} The built websocket url.
   */
  buildURL(): string {
    const csrftoken = getCookie("csrftoken");
    if (!csrftoken) {
      throw new Error(
        "No csrftoken found, please ensure you are logged into MAAS."
      );
    }
    const { hostname, port } = window.location;
    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    return `${protocol}//${hostname}:${port}${
      import.meta.env.VITE_APP_BASENAME
    }/ws?csrftoken=${csrftoken}`;
  }

  /**
   * Get the next available request id.
   * @returns {Integer} An id.
   */
  _getId(): WebSocketRequest["request_id"] {
    const id = this._nextId;
    this._nextId++;
    return id;
  }

  /**
   * Store a mapping of id to action type.
   * @param {Object} action - A Redux action.
   * @returns {Integer} The id that was created.
   */
  _addRequest(action: WebSocketAction): WebSocketRequest["request_id"] {
    const id = this._getId();
    this._requests.set(id, action);
    return id;
  }

  /**
   * Create a reconnecting websocket and connect to it.
   * @returns {Object} The websocket that was created.
   */
  connect(): ReconnectingWebSocket {
    this.rws = new ReconnectingWebSocket(this.buildURL(), undefined, {
      debug: import.meta.env.VITE_APP_WEBSOCKET_DEBUG === "true",
      // Limit message backlog on reconnection to prevent overwhelming the server
      // with a flood of queued messages when the connection is re-established.
      // Typical page load generates 5-25 messages; buffer allows for additional user actions.
      maxEnqueuedMessages: 30,
    });
    return this.rws;
  }

  /**
   * Get a base action type from a given id.
   * @param {Integer} id - A request id.
   * @returns {Object} A Redux action.
   */
  getRequest(id: WebSocketRequest["request_id"]): WebSocketAction | null {
    return this._requests.get(id) || null;
  }

  /**
   * Send a websocket message.
   * @param {String} action - A base Redux action type.
   * @param {Object} message - The message content.
   */
  send(
    action: WebSocketAction,
    message: WebSocketRequestMessage
  ): WebSocketRequest["request_id"] {
    const id = this._addRequest(action);
    const payload = {
      ...message,
      request_id: id,
    };
    if (this.rws) {
      this.rws.send(JSON.stringify(payload));
    }
    return id;
  }
}

export default WebSocketClient;
