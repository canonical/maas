import { default as controllers } from "@/app/controllers/urls";
import { default as devices } from "@/app/devices/urls";
import { default as domains } from "@/app/domains/urls";
import { default as images } from "@/app/images/urls";
import { default as intro } from "@/app/intro/urls";
import { default as kvm } from "@/app/kvm/urls";
import { default as machines } from "@/app/machines/urls";
import { default as networkDiscovery } from "@/app/networkDiscovery/urls";
import { default as networks } from "@/app/networks/urls";
import { default as pools } from "@/app/pools/urls";
import { default as preferences } from "@/app/preferences/urls";
import { default as racks } from "@/app/racks/urls";
import { default as settings } from "@/app/settings/urls";
import { default as switches } from "@/app/switches/urls";
import { default as tags } from "@/app/tags/urls";
import { default as zones } from "@/app/zones/urls";

const urls = {
  index: "/",
  login: "/login",
  loginCallback: "/login/oidc/callback",
  controllers,
  networkDiscovery,
  devices,
  domains,
  images,
  intro,
  kvm,
  machines,
  pools,
  racks,
  switches,
  preferences,
  settings,
  networks,
  tags,
  zones,
} as const;

export default urls;
