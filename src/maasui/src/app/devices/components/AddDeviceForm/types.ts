import type { ZoneResponse } from "@/app/apiclient";
import type {
  CreateParams,
  Device,
  DeviceIpAssignment,
} from "@/app/store/device/types";
import type { Domain } from "@/app/store/domain/types";

type CreateParamsInterface = CreateParams["interfaces"][0];

export type AddDeviceInterface = {
  id: number;
  ip_address: NonNullable<CreateParamsInterface["ip_address"]>;
  ip_assignment: DeviceIpAssignment;
  mac: CreateParamsInterface["mac"];
  name: NonNullable<CreateParamsInterface["name"]>;
  subnet: string;
  subnet_cidr: string;
};

export type AddDeviceValues = {
  domain: Domain["name"];
  hostname: Device["hostname"];
  interfaces: (Omit<AddDeviceInterface, "subnet"> & { subnet: string })[];
  zone: ZoneResponse["name"];
};
